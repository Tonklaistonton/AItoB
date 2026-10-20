"""AItoB unified agent: permission-filtered tools over authenticated MCP."""
import argparse
import asyncio
import copy
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, "/gateway")
from auth import authenticate
from aitob_agent_policy import TOOL_FIELDS, eligible_tool_names

TURN_URL = "http://host.docker.internal:8000/assistant/turn"
MAX_CALLS = 4
MAX_READS = 2
EXCERPT_CHARS = 1000
ALLOWED = TOOL_FIELDS


def post_turn(key, messages):
    request = urllib.request.Request(
        TURN_URL,
        data=json.dumps({"messages": messages}).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=200) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError("Gateway returned HTTP " + str(error.code)) from None
    except (urllib.error.URLError, OSError, ValueError):
        raise RuntimeError("Gateway unavailable or returned invalid JSON") from None


def validate_call(call, found_ids, allowed_names):
    if not isinstance(call, dict) or not isinstance(call.get("function"), dict):
        raise RuntimeError("Malformed tool call")
    function = call["function"]
    name, arguments = function.get("name"), function.get("arguments")
    if name not in ALLOWED:
        raise RuntimeError("Model requested an unknown tool")
    if name not in allowed_names:
        raise PermissionError("Model requested a tool outside the allowlist")
    if not isinstance(arguments, dict) or set(arguments) != ALLOWED[name]:
        raise RuntimeError("Unexpected tool arguments; nothing executed")
    if name == "search_emails":
        query, limit = arguments["query"], arguments["max_results"]
        if (not isinstance(query, str) or not 1 <= len(query.strip()) <= 300
                or type(limit) is not int or not 1 <= limit <= 3):
            raise RuntimeError("Invalid search arguments")
    elif name == "read_email":
        message_id = arguments["message_id"]
        if (not isinstance(message_id, str)
                or re.fullmatch(r"[A-Za-z0-9_-]{1,128}", message_id) is None
                or message_id not in found_ids):
            raise RuntimeError("Read rejected: message ID was not returned by this chat's search")
    elif name == "search_company_docs":
        query = arguments["query"]
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 300:
            raise RuntimeError("Invalid document query")
    return name, arguments


def prepare_result(name, arguments, data, found_ids, sources):
    if not isinstance(data, dict):
        raise RuntimeError("Invalid MCP result")
    if name == "search_company_docs":
        documents = data.get("documents")
        if (not isinstance(documents, list) or data.get("count") != len(documents)
                or len(documents) > 2):
            raise RuntimeError("Invalid document results")
        excerpts = []
        for document in documents:
            if (not isinstance(document, dict)
                    or not all(isinstance(document.get(field), str) for field in ("id", "title", "content"))
                    or not isinstance(document.get("truncated"), bool)):
                raise RuntimeError("Invalid document record")
            excerpt = dict(document)
            excerpt["content"] = document["content"][:600]
            excerpt["truncated"] = document["truncated"] or len(document["content"]) > 600
            excerpts.append(excerpt)
            sources[document["id"]] = {"id": document["id"], "title": document["title"],
                                       "kind": "document", "truncated": excerpt["truncated"]}
        return {"documents": excerpts, "count": len(excerpts)}
    if name == "clean_finance_expenses":
        counts = ("input_rows", "cleaned_rows", "duplicate_rows", "rejected_rows")
        if (not all(type(data.get(field)) is int and data[field] >= 0 for field in counts)
                or data["input_rows"] != sum(data[field] for field in counts[1:])
                or not isinstance(data.get("total_amount"), str) or data.get("currency") != "THB"):
            raise RuntimeError("Invalid CSV report")
        report = {field: data[field] for field in counts + ("total_amount", "currency")}
        report["source_id"] = "finance-expenses"
        sources["finance-expenses"] = {"id": "finance-expenses", "title": "Cleaned Finance expenses CSV",
                                       "kind": "csv", "truncated": False}
        return report
    if data.get("scope_label") != "AItoB-Demo":
        raise RuntimeError("Unexpected MCP result scope")
    if name == "search_emails":
        references = data.get("results")
        if (not isinstance(references, list) or data.get("count") != len(references)
                or len(references) > arguments["max_results"]):
            raise RuntimeError("Invalid search result")
        for item in references:
            if (not isinstance(item, dict) or not isinstance(item.get("id"), str)
                    or re.fullmatch(r"[A-Za-z0-9_-]{1,128}", item["id"]) is None):
                raise RuntimeError("Invalid message reference")
        found_ids.update(item["id"] for item in references)
        return data

    email = data.get("email")
    if (not isinstance(email, dict) or email.get("id") != arguments["message_id"]
            or not all(isinstance(email.get(field), str)
                       for field in ("subject", "from", "date", "body"))
            or not email["body"].strip() or len(email["body"]) > 2000
            or not isinstance(email.get("truncated"), bool)):
        raise RuntimeError("Invalid email result")
    excerpt = {field: email[field] for field in ("id", "subject", "from", "date")}
    excerpt["body"] = email["body"][:EXCERPT_CHARS]
    excerpt["truncated"] = email["truncated"] or len(email["body"]) > EXCERPT_CHARS
    sources[email["id"]] = {
        "id": email["id"], "subject": email["subject"],
        "kind": "email",
        "truncated": excerpt["truncated"],
    }
    return {"email": excerpt, "scope_label": "AItoB-Demo"}


async def _run_agent_impl(key, question, progress=None, history=None):
    identity = authenticate("Bearer " + key)
    if identity is None:
        raise PermissionError("invalid_or_missing_api_key")
    allowed_names = eligible_tool_names(identity)
    if not allowed_names:
        raise PermissionError("assistant_access_denied")
    if not isinstance(question, str) or not 1 <= len(question.strip()) <= 1000:
        raise ValueError("Question must contain 1 to 1000 characters")

    if history is None:
        history = []
    if not isinstance(history, list) or len(history) > 2:
        raise ValueError("Invalid recent history")
    for item in history:
        if (not isinstance(item, dict) or set(item) != {"role", "content"}
                or item["role"] not in ("user", "assistant")
                or not isinstance(item["content"], str)
                or not 1 <= len(item["content"]) <= 1000):
            raise ValueError("Invalid recent history message")

    # Imported only after authorization; no MCP connection exists before this guard.
    from mcp import Client, StdioServerParameters

    server = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).resolve().parent / "aitob_tools_server.py")],
        env={"AITOB_API_KEY": key},
    )
    messages = [dict(item) for item in history] + [{"role": "user", "content": question.strip()}]
    found_ids, sources, trace = set(), {}, []
    call_count = read_count = 0
    csv_count = 0
    requested_clean = any(word in question.casefold() for word in
                          ("ทำความสะอาด", "clean", "ล้างข้อมูล", "ประมวลผล"))
    requested_dataset = any(word in question.casefold() for word in ("csv", "ค่าใช้จ่าย", "expenses"))

    async with Client(server) as client:
        discovered = await client.list_tools()
        schemas = {tool.name: tool.input_schema for tool in discovered.tools}
        for name, fields in ALLOWED.items():
            if name not in schemas or set(schemas[name].get("properties", {})) != fields:
                raise RuntimeError("MCP tool definitions do not match the application")

        for turn in range(1, MAX_CALLS + 2):
            if progress:
                progress("MODEL TURN " + str(turn))
            response = await asyncio.to_thread(post_turn, key, copy.deepcopy(messages))
            message = response.get("message")
            if not isinstance(message, dict) or message.get("role") != "assistant":
                raise RuntimeError("Invalid model response")
            content = message.get("content", "")
            calls = message.get("tool_calls") or []
            if not isinstance(content, str) or not isinstance(calls, list):
                raise RuntimeError("Invalid assistant content or calls")

            if not calls:
                if not content.strip():
                    raise RuntimeError("Model returned no answer")
                return {
                    "status": "incomplete" if response.get("done_reason") == "length" else "complete",
                    "answer": content,
                    "sources": list(sources.values()),
                    "trace": trace,
                }

            if len(calls) > 3 or call_count + len(calls) > MAX_CALLS:
                raise RuntimeError("Tool budget reached; stopped without more tool calls")
            checked = [validate_call(call, found_ids, allowed_names) for call in calls]
            if read_count + sum(name == "read_email" for name, _ in checked) > MAX_READS:
                raise RuntimeError("Read limit reached: this lab permits two reads per chat")
            proposed_csv = sum(name == "clean_finance_expenses" for name, _ in checked)
            if proposed_csv and (not requested_clean or not requested_dataset):
                raise RuntimeError("CSV cleaning requires an explicit cleaning request for CSV/expenses")
            if csv_count + proposed_csv > 1:
                raise RuntimeError("CSV may be cleaned only once per request")

            messages.append({"role": "assistant", "content": content, "tool_calls": calls})
            for call, (name, arguments) in zip(calls, checked):
                call_count += 1
                read_count += name == "read_email"
                csv_count += name == "clean_finance_expenses"
                if progress:
                    progress("MCP TOOL: " + name)
                result = await client.call_tool(name, arguments, read_timeout_seconds=120)
                if result.is_error:
                    raise RuntimeError("MCP tool failed: " + name + "; no result was used")
                data = prepare_result(name, arguments, result.structured_content, found_ids, sources)
                trace.append({"tool": name, "status": "ok"})
                tool_message = {
                    "role": "tool", "tool_name": name,
                    "content": json.dumps(data, ensure_ascii=False),
                }
                if isinstance(call.get("id"), str):
                    tool_message["tool_call_id"] = call["id"]
                messages.append(tool_message)

    raise RuntimeError("Agent round limit reached")



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


def main():
    parser = argparse.ArgumentParser(description="Trusted administrator's CLI test; not a user login UI")
    parser.add_argument("--key", choices=["finance", "hr"], default="finance")
    parser.add_argument("--question", default="บริษัทให้วันลาพักร้อนกี่วัน และต้องแจ้งล่วงหน้ากี่วัน")
    args = parser.parse_args()
    key = (Path("/gateway/credentials") / (args.key + ".key")).read_text().strip()
    try:
        result = asyncio.run(asyncio.wait_for(
            run_agent(key, args.question, progress=lambda text: print(text, flush=True)), timeout=1200
        ))
    except (PermissionError, ValueError, RuntimeError, TimeoutError) as error:
        print("STOP:", str(error), flush=True)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] == "complete" and result["trace"] and result["sources"]:
        print("PASS: Unified agent used MCP and produced an answer with source records.")
    else:
        print("CHECK: No completed tool-backed answer; inspect permissions, answer and trace.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
