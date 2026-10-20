import json
import urllib.request

tool = {
    "type": "function",
    "function": {
        "name": "search_emails",
        "description": (
            "Search the authenticated user's allowed email collection "
            "using Gmail search syntax. Returns message references. "
            "Use this before claiming facts about mailbox contents."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Gmail search query, for example from:canva.com"
                },
                "max_results": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "description": "Maximum messages to retrieve"
                }
            },
            "required": ["query", "max_results"],
            "additionalProperties": False
        }
    }
}

payload = {
    "model": "gemma4:12b",
    "messages": [
        {
            "role": "system",
            "content": (
                "You are an email assistant. Use the available tool "
                "when a request requires searching email. "
                "Do not invent search results. "
                "User identity and access permissions are handled "
                "by the application, not by tool arguments."
            )
        },
        {
            "role": "user",
            "content": "ช่วยค้นหาอีเมลจาก Canva ให้หน่อย ขอไม่เกิน 3 ฉบับ"
        }
    ],
    "tools": [tool],
    "stream": False,
    "think": False,
    "options": {"num_ctx": 4096, "num_predict": 512}
}

request = urllib.request.Request(
    "http://127.0.0.1:11434/api/chat",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST"
)

with urllib.request.urlopen(request, timeout=180) as response:
    result = json.load(response)

message = result.get("message", {})
print("Assistant message:")
print(json.dumps(message, ensure_ascii=False, indent=2))
print("Done reason:", result.get("done_reason"))

calls = message.get("tool_calls", [])
assert len(calls) == 1, "Expected exactly one native tool call."

function = calls[0]["function"]
assert function["name"] == "search_emails", "Unexpected tool name."

arguments = function["arguments"]
assert isinstance(arguments, dict), "Arguments must be an object."
assert set(arguments) == {"query", "max_results"}, "Unexpected arguments."
assert isinstance(arguments["query"], str)
assert arguments["query"].strip(), "Query must not be empty."
assert "canva" in arguments["query"].casefold()
assert type(arguments["max_results"]) is int
assert arguments["max_results"] == 3

print("PASS: Model selected search_emails with valid arguments.")
print("No MCP tools were executed and no Gmail messages were fetched.")
