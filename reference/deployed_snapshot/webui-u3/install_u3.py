"""Add the local chat service and bounded recent-history support to U2."""
import datetime
from pathlib import Path
import shutil

package = Path(__file__).resolve().parent
folder = Path.home() / "aitob-lab" / "mcp-lab"
agent = folder / "aitob_agent.py"
source = agent.read_text(encoding="utf-8")
signature = "async def run_agent(key, question, progress=None):"
messages = '    messages = [{"role": "user", "content": question.strip()}]'
anchor = "    # Imported only after authorization; no MCP connection exists before this guard.\n"

if "progress=None, history=None" in source:
    raise SystemExit("U3 history support appears installed already; no files changed.")
if any(source.count(item) != 1 for item in (signature, messages, anchor)):
    raise SystemExit("Agent differs from the expected U2 version; no files changed.")

validation = '''    if history is None:
        history = []
    if not isinstance(history, list) or len(history) > 2:
        raise ValueError("Invalid recent history")
    for item in history:
        if (not isinstance(item, dict) or set(item) != {"role", "content"}
                or item["role"] not in ("user", "assistant")
                or not isinstance(item["content"], str)
                or not 1 <= len(item["content"]) <= 1000):
            raise ValueError("Invalid recent history message")

'''
updated = source.replace(signature, "async def run_agent(key, question, progress=None, history=None):", 1)
updated = updated.replace(anchor, validation + anchor, 1)
updated = updated.replace(messages, '    messages = [dict(item) for item in history] + [{"role": "user", "content": question.strip()}]', 1)
compile(updated, str(agent), "exec")

names = ("aitob_assistant_service.py", "check_u3_service.py")
for name in names:
    content = (package / name).read_text(encoding="utf-8")
    compile(content, name, "exec")
    destination = folder / name
    if destination.exists() and destination.read_text(encoding="utf-8") != content:
        raise SystemExit("Existing file differs; no files changed: " + name)

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
shutil.copy2(agent, folder / ("aitob_agent_before_u3_" + stamp + ".py"))
for name in names:
    shutil.copy2(package / name, folder / name)
agent.write_text(updated, encoding="utf-8")
print("PASS: Chat service installed; recent history limited to two messages.")
print("The existing gateway does not need restarting for this step.")
