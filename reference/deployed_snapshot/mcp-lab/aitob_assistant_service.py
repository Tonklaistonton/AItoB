"""Local HTTP bridge for Open WebUI. Bearer keys remain per-user."""
import asyncio
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, "/gateway")
from auth import authenticate
from aitob_finance_export import export_for_key
from aitob_finance_upload import authorize_upload, process_for_key
from aitob_agent_policy import eligible_tool_names
from aitob_agent import run_agent

BUSY = threading.Lock()


def authorize(authorization):
    scheme, separator, key = authorization.partition(" ")
    if scheme.lower() != "bearer" or not separator or not key:
        return 401, None, None
    identity = authenticate("Bearer " + key)
    if identity is None:
        return 401, None, None
    if not eligible_tool_names(identity):
        return 403, None, None
    return 200, identity, key


def validate_arguments(arguments):
    if not isinstance(arguments, dict) or set(arguments) - {"question", "history"}:
        raise ValueError("invalid_chat_arguments")
    question = arguments.get("question")
    history = arguments.get("history", [])
    if not isinstance(question, str) or not 1 <= len(question.strip()) <= 1000:
        raise ValueError("question_must_be_1_to_1000_characters")
    if not isinstance(history, list) or len(history) > 2:
        raise ValueError("invalid_history")
    for item in history:
        if (not isinstance(item, dict) or set(item) != {"role", "content"}
                or item["role"] not in ("user", "assistant")
                or not isinstance(item["content"], str)
                or not 1 <= len(item["content"]) <= 1000):
            raise ValueError("invalid_history_message")
    return question.strip(), history


async def chat_for_key(authorization, arguments):
    status, identity, key = authorize(authorization)
    if status != 200:
        return status, {"error": "invalid_key_or_permissions"}
    try:
        question, history = validate_arguments(arguments)
    except ValueError as error:
        return 400, {"error": str(error)}
    try:
        result = await asyncio.wait_for(run_agent(key, question, history=history), timeout=1200)
    except TimeoutError:
        return 504, {"error": "assistant_timeout"}
    except PermissionError:
        return 403, {"error": "assistant_access_denied"}
    except (RuntimeError, ValueError):
        return 502, {"error": "assistant_job_failed"}
    return 200, result


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, result):
        body = json.dumps(result, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self.reply(200, {"status": "ok", "service": "aitob-assistant"})
        else:
            self.reply(404, {"error": "not_found"})

    def do_POST(self):
        if self.path not in ("/chat", "/finance/export", "/finance/authorize", "/finance/upload"):
            self.reply(404, {"error": "not_found"})
            return
        authorization = self.headers.get("Authorization", "")
        status, _, _ = authorize(authorization)
        if status != 200:
            self.reply(status, {"error": "invalid_key_or_permissions"})
            return
        if self.path in ("/finance/authorize", "/finance/upload"):
            finance_status, result = authorize_upload(authorization)
            if finance_status != 200:
                self.reply(finance_status, result)
                return
        try:
            self.connection.settimeout(15)
            length = int(self.headers.get("Content-Length", "0"))
            limit = 1400000 if self.path == "/finance/upload" else 32768
            if not 0 < length <= limit:
                raise ValueError()
            arguments = json.loads(self.rfile.read(length))
            if self.path == "/chat":
                validate_arguments(arguments)
            elif self.path == "/finance/upload":
                if not isinstance(arguments, dict) or set(arguments) != {"filename", "content_base64"}:
                    raise ValueError("invalid_upload_arguments")
            elif arguments != {}:
                raise ValueError("invalid_export_arguments")
        except (ValueError, UnicodeDecodeError, OSError):
            self.reply(400, {"error": "invalid_request_body"})
            return
        if not BUSY.acquire(blocking=False):
            self.reply(409, {"error": "assistant_busy"})
            return
        try:
            try:
                if self.path == "/finance/authorize":
                    status, result = authorize_upload(authorization)
                elif self.path == "/finance/upload":
                    status, result = process_for_key(authorization, arguments)
                elif self.path == "/finance/export":
                    status, result = export_for_key(authorization)
                else:
                    status, result = asyncio.run(chat_for_key(authorization, arguments))
            except Exception as error:
                print("ASSISTANT ERROR:", type(error).__name__, flush=True)
                status, result = 500, {"error": "assistant_internal_error"}
            self.reply(status, result)
        finally:
            BUSY.release()


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", 8002), Handler)
    print("READY: AItoB Assistant service on container port 8002", flush=True)
    server.serve_forever()
