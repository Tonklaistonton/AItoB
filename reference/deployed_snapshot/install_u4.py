"""Repair permission error reporting without weakening tool authorization."""
import ast
import datetime
from pathlib import Path
import shutil


WRAPPER = '''
def _permission_only(error):
    if isinstance(error, BaseExceptionGroup):
        return bool(error.exceptions) and all(_permission_only(item) for item in error.exceptions)
    return isinstance(error, PermissionError)


async def run_agent(key, question, progress=None, history=None):
    try:
        return await _run_agent_impl(key, question, progress=progress, history=history)
    except ExceptionGroup as error:
        if _permission_only(error):
            raise PermissionError("assistant_access_denied") from None
        raise


'''

PROMPT = '''SYSTEM + (
            "\\nThe only tools permitted for this request are: " + ", ".join(sorted(allowed)) + ". "
            "Tool-specific instructions above apply ONLY when the tool is permitted. "
            "For unavailable tools, explain in Thai that current permissions do not allow the operation. "
            "Never claim you can use an unavailable tool or ask for an upload to bypass permissions. "
            "If company document search is empty, say no matching documents were found among documents "
            "this user can access; do not claim the documents do not exist company-wide."
        )'''


def updates(agent, turn):
    signature = "async def run_agent(key, question, progress=None, history=None):"
    old = '''    if name not in ALLOWED or name not in allowed_names:
        raise RuntimeError("Model requested a tool outside the allowlist")'''
    new = '''    if name not in ALLOWED:
        raise RuntimeError("Model requested an unknown tool")
    if name not in allowed_names:
        raise PermissionError("Model requested a tool outside the allowlist")'''
    anchor = "def main():"
    prompt_anchor = '"content": SYSTEM}'
    if any(agent.count(item) != 1 for item in (signature, old, anchor)):
        raise ValueError("Unexpected agent version; stopped without changes.")
    if turn.count(prompt_anchor) != 1:
        raise ValueError("Unexpected gateway turn version; stopped without changes.")
    agent = agent.replace(signature, signature.replace("run_agent(", "_run_agent_impl("), 1)
    agent = agent.replace(old, new, 1).replace(anchor, WRAPPER + anchor, 1)
    turn = turn.replace(prompt_anchor, '"content": ' + PROMPT + '}', 1)
    compile(agent, "aitob_agent.py", "exec")
    compile(turn, "aitob_turn.py", "exec")
    return agent, turn


def verify(agent):
    # Exercise the real patched validator and wrapper without opening any connections.
    tree = ast.parse(agent)
    names = {"validate_call", "_permission_only", "run_agent"}
    selected = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name in names]
    namespace = {"ALLOWED": {"search_emails": {"query", "max_results"}}}
    exec(compile(ast.Module(body=selected, type_ignores=[]), "patched_checks", "exec"), namespace)
    try:
        namespace["validate_call"](
            {"function": {"name": "search_emails", "arguments": {"query": "Canva", "max_results": 1}}},
            set(), {"search_company_docs"})
    except PermissionError:
        pass
    else:
        raise AssertionError("Unauthorized tool was not denied")

    async def denied(*args, **kwargs):
        raise ExceptionGroup("outer", [ExceptionGroup("inner", [PermissionError("denied")])])

    namespace["_run_agent_impl"] = denied
    coroutine = namespace["run_agent"]("test-placeholder", "test")
    try:
        coroutine.send(None)
    except PermissionError:
        pass
    else:
        raise AssertionError("Nested permission error was not mapped")
    finally:
        coroutine.close()

    mixed = ExceptionGroup("mixed", [PermissionError("denied"), RuntimeError("unrelated")])
    assert not namespace["_permission_only"](mixed)
    assert not namespace["_permission_only"](RuntimeError("unrelated"))
    print("PASS: Unauthorized tool denied before tool execution.")
    print("PASS: Nested permission errors mapped; unrelated failures preserved.")


def main():
    base = Path.home() / "aitob-lab"
    agent_path = base / "mcp-lab" / "aitob_agent.py"
    turn_path = base / "gateway" / "aitob_turn.py"
    agent, turn = updates(agent_path.read_text(encoding="utf-8"), turn_path.read_text(encoding="utf-8"))
    verify(agent)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    for path in (agent_path, turn_path):
        shutil.copy2(path, path.with_name(path.stem + "_before_u4_" + stamp + ".py"))
    agent_path.write_text(agent, encoding="utf-8")
    turn_path.write_text(turn, encoding="utf-8")
    print("PASS: U4 installed with backups; permission rules remain enforced.")
    print("Restart gateway port 8000 and Assistant service port 8002.")
    print("No Gmail, LLM or CSV operations were performed by this installer.")


if __name__ == "__main__":
    main()
