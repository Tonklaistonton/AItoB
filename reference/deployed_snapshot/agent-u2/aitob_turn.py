"""Gateway inference endpoint for the unified agent; never executes tools."""
import json
import socket
import urllib.error
import urllib.request
from aitob_agent_policy import SYSTEM, eligible_tool_names, tools_for


def assistant_turn(identity, arguments, model, ollama_url):
    allowed = eligible_tool_names(identity)
    if not allowed:
        return 403, {"error": "assistant_access_denied"}
    if not isinstance(arguments, dict) or set(arguments) != {"messages"}:
        return 400, {"error": "expected_messages"}
    messages = arguments["messages"]
    if not isinstance(messages, list) or not 1 <= len(messages) <= 16:
        return 400, {"error": "invalid_message_history"}
    fields = {"role", "content", "tool_calls", "tool_name", "tool_call_id"}
    for message in messages:
        if (not isinstance(message, dict) or set(message) - fields
                or message.get("role") not in ("user", "assistant", "tool")
                or not isinstance(message.get("content", ""), str)):
            return 400, {"error": "invalid_chat_message"}
        if "tool_calls" in message:
            calls = message["tool_calls"]
            if (message["role"] != "assistant" or not isinstance(calls, list)
                    or not 1 <= len(calls) <= 3):
                return 400, {"error": "invalid_tool_history"}
            for call in calls:
                if (not isinstance(call, dict) or not isinstance(call.get("function"), dict)
                        or call["function"].get("name") not in allowed
                        or not isinstance(call["function"].get("arguments"), dict)):
                    return 403, {"error": "tool_not_permitted"}
        if message["role"] == "tool" and message.get("tool_name") not in allowed:
            return 403, {"error": "tool_not_permitted"}
    if len(json.dumps(messages).encode("utf-8")) > 24000:
        return 400, {"error": "chat_history_too_large"}
    payload = {
        "model": model, "messages": [{"role": "system", "content": SYSTEM}] + messages,
        "tools": tools_for(identity), "stream": False, "think": False,
        "options": {"num_ctx": 4096, "num_predict": 512},
    }
    request = urllib.request.Request(
        ollama_url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            result = json.load(response)
        message = result["message"]
        if not isinstance(message, dict) or message.get("role") != "assistant":
            raise ValueError("Invalid assistant message")
    except (TimeoutError, socket.timeout):
        return 504, {"error": "ollama_timeout"}
    except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError):
        return 502, {"error": "ollama_unavailable_or_invalid_response"}
    return 200, {"message": message, "done_reason": result.get("done_reason")}


def handle_assistant_http(handler, identity, model, ollama_url):
    if not eligible_tool_names(identity):
        return 403, {"error": "assistant_access_denied"}
    try:
        length = int(handler.headers.get("Content-Length", "0"))
        if not 0 < length <= 32768:
            raise ValueError()
        arguments = json.loads(handler.rfile.read(length))
    except (ValueError, UnicodeDecodeError):
        return 400, {"error": "invalid_request_body"}
    return assistant_turn(identity, arguments, model, ollama_url)
