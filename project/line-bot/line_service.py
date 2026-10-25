"""AItoB LINE Bot Gateway Bridge.
Receives LINE Webhooks with fail-closed HMAC-SHA256 signature verification.
Routes user questions to AItoB Assistant/Gateway using per-user Bearer token.
"""
import base64
import hashlib
import hmac
import json
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("LINE_BOT_PORT", "8003"))
CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "").strip()
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
ASSISTANT_URL = os.environ.get("ASSISTANT_URL", "http://assistant:8002").rstrip("/")
AITOB_API_KEY = os.environ.get("AITOB_API_KEY", "").strip()


def verify_signature(secret: str, body: bytes, signature: str) -> bool:
    if not secret or not signature:
        return False
    mac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(mac).decode("utf-8")
    return hmac.compare_digest(expected, signature.strip())


def ask_assistant(question: str) -> str:
    if not AITOB_API_KEY:
        return "ระบบ AItoB ยังไม่ได้ตั้งค่า AITOB_API_KEY"
    payload = json.dumps({"question": question, "history": []}).encode("utf-8")
    req = urllib.request.Request(
        f"{ASSISTANT_URL}/chat",
        data=payload,
        headers={
            "Authorization": f"Bearer {AITOB_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.load(resp)
            return data.get("answer") or "ไม่มีข้อมูลคำตอบจากผู้ช่วย"
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as err:
        print(f"Assistant query error: {err}", flush=True)
        return "ขออภัย ระบบผู้ช่วย AI ขัดข้องชั่วคราว กรุณาลองใหม่ภายหลัง"


def reply_line(reply_token: str, text: str) -> bool:
    if not CHANNEL_ACCESS_TOKEN or not reply_token:
        return False
    payload = json.dumps({
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text[:4900]}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.line.me/v2/bot/message/reply",
        data=payload,
        headers={
            "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError) as err:
        print(f"LINE reply error: {err}", flush=True)
        return False


class LineWebhookHandler(BaseHTTPRequestHandler):
    def reply_json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self.reply_json(200, {"status": "ok", "service": "aitob-line-bot"})
        else:
            self.reply_json(404, {"error": "not_found"})

    def do_POST(self):
        if self.path not in ("/webhook", "/line/webhook"):
            self.reply_json(404, {"error": "not_found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 131072:
                self.reply_json(400, {"error": "invalid_content_length"})
                return
            body = self.rfile.read(length)
        except (ValueError, OSError):
            self.reply_json(400, {"error": "read_error"})
            return

        # Fail-closed signature check
        sig = self.headers.get("X-Line-Signature", "")
        if not CHANNEL_SECRET or not verify_signature(CHANNEL_SECRET, body, sig):
            self.reply_json(403, {"error": "invalid_signature"})
            return

        try:
            payload = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self.reply_json(400, {"error": "invalid_json"})
            return

        # Acknowledge webhook receipt to LINE platform
        self.reply_json(200, {"status": "received"})

        # Dispatch events
        events = payload.get("events", [])
        if not isinstance(events, list):
            return

        for ev in events:
            if not isinstance(ev, dict):
                continue
            if ev.get("type") == "message" and ev.get("message", {}).get("type") == "text":
                user_msg = (ev.get("message", {}).get("text") or "").strip()
                reply_token = ev.get("replyToken")
                if user_msg and reply_token:
                    answer = ask_assistant(user_msg)
                    reply_line(reply_token, answer)


def run_server():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), LineWebhookHandler)
    print(f"AItoB LINE Bot Gateway listening on port {PORT}...", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    run_server()