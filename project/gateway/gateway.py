import json
import os
import socket
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

from aitob_turn import handle_assistant_http
from mail_agent_turn import handle_turn_http
from email_workflow import run_email_summary
from workflow_api import run_expenses_with_summary
from rag import answer_rag
from search import handle_search
from documents import DOCUMENTS, can_read
from auth import authenticate

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:12b")
HOST = os.environ.get("GATEWAY_HOST", "0.0.0.0")
PORT = int(os.environ.get("GATEWAY_PORT", "8000"))


class Gateway(BaseHTTPRequestHandler):
    def reply(self, status, result):
        body = json.dumps(result, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self.reply(200, {"status": "ok", "service": "aitob-gateway"})
            return

        if self.path.split("?", 1)[0] == "/search":
            status, result = handle_search(
                self.path,
                self.headers.get("Authorization", "")
            )
            self.reply(status, result)
            return

        if not self.path.startswith("/documents/"):
            self.reply(404, {"error": "not_found"})
            return

        identity = authenticate(self.headers.get("Authorization", ""))
        if identity is None:
            self.reply(401, {"error": "invalid_or_missing_api_key"})
            return

        document_id = self.path[len("/documents/"):]
        document = DOCUMENTS.get(document_id)
        if document is None:
            self.reply(404, {"error": "document_not_found"})
            return

        if not can_read(identity, document):
            print("DOCUMENT DENIED: user=" + identity["user"], flush=True)
            self.reply(403, {"error": "document_access_denied"})
            return

        self.reply(200, {"document": document, "identity": identity})

    def do_POST(self):
        if self.path not in ("/chat", "/rag", "/workflow/expenses", "/email/summary", "/agent/turn", "/assistant/turn"):
            self.reply(404, {"error": "not_found"})
            return

        identity = authenticate(self.headers.get("Authorization", ""))
        if identity is None:
            print("AUTH DENIED: Ollama not called", flush=True)
            self.reply(401, {"error": "invalid_or_missing_api_key"})
            return

        if self.path == "/assistant/turn":
            status, result = handle_assistant_http(
                self, identity, MODEL, OLLAMA_URL
            )
            self.reply(status, result)
            return

        if self.path == "/agent/turn":
            status, result = handle_turn_http(
                self, identity, MODEL, OLLAMA_URL
            )
            self.reply(status, result)
            return

        if self.path == "/email/summary":
            status, result = run_email_summary(
                identity,
                self.headers.get("Authorization", ""),
                MODEL,
                OLLAMA_URL
            )
            self.reply(status, result)
            return

        if self.path == "/workflow/expenses":
            status, result = run_expenses_with_summary(identity, MODEL, OLLAMA_URL)
            self.reply(status, result)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16384:
                self.reply(400, {"error": "body_must_be_1_to_16384_bytes"})
                return

            data = json.loads(self.rfile.read(length))
            question = data.get("question") if isinstance(data, dict) else None
            if not isinstance(question, str) or not question.strip():
                self.reply(400, {"error": "question_must_be_nonempty_text"})
                return
        except (ValueError, UnicodeDecodeError):
            self.reply(400, {"error": "invalid_json_or_content_length"})
            return

        if self.path == "/rag":
            status, result = answer_rag(
                identity, question, MODEL, OLLAMA_URL
            )
            self.reply(status, result)
            return

        payload = {
            "model": MODEL,
            "messages": [{"role": "user", "content": question}],
            "stream": False,
            "think": False,
            "options": {"num_ctx": 4096, "num_predict": 256}
        }
        request = urllib.request.Request(
            OLLAMA_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        print("CALL OLLAMA: user=" + identity["user"], flush=True)
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                result = json.load(response)
            answer = result["message"]["content"]
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError("Empty model response")
        except (TimeoutError, socket.timeout):
            self.reply(504, {"error": "ollama_timeout"})
            return
        except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError):
            self.reply(502, {"error": "ollama_unavailable_or_invalid_response"})
            return

        self.reply(200, {
            "model": MODEL,
            "answer": answer,
            "via": "aitob-gateway",
            "identity": identity
        })


if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), Gateway)
    print(f"AItoB Gateway: http://{HOST}:{PORT}", flush=True)
    server.serve_forever()
