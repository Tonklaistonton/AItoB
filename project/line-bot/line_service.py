import base64
import hashlib
import hmac
import json
import os
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
PORT = int(os.environ.get("LINE_BOT_PORT", "8003"))

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://gateway:8000")
AITOB_API_KEY = os.environ.get("AITOB_API_KEY", "ivJk7sczEm3PlNE1rsBcPdP2RTvKWzYEdDJaCEiqd4M")

# Direct LLM fallback (e.g. 9router / OpenAI / Ollama)
LLM_API_BASE_URL = os.environ.get("LLM_API_BASE_URL", "https://rh7669c.abc-tunnel.us/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "sk-dec6393f10b69e7c-h0ukrj-57d33abf")
LLM_MODEL = os.environ.get("LLM_MODEL", "ag/gemini-3.8-flash-high")


def verify_signature(channel_secret: str, body: bytes, signature: str) -> bool:
    if not channel_secret or not signature:
        return False
    mac = hmac.new(channel_secret.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(mac).decode("utf-8")
    return hmac.compare_digest(expected, signature)


def show_loading(user_id: str, access_token: str):
    if not access_token or not user_id:
        return
    url = "https://api.line.me/v2/bot/chat/loading/start"
    payload = json.dumps({"chatId": user_id, "loadingSeconds": 30}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "Mozilla/5.0"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5):
            pass
    except Exception:
        pass


def reply_line(reply_token: str, text: str, access_token: str):
    if not access_token or not reply_token:
        print("Missing LINE_CHANNEL_ACCESS_TOKEN or reply_token, skipping LINE push", flush=True)
        return
    url = "https://api.line.me/v2/bot/message/reply"
    safe_text = text[:4900] if len(text) > 4900 else text
    payload = json.dumps({
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": safe_text}]
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "Mozilla/5.0"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status
    except Exception as e:
        print(f"Error sending LINE reply: {e}", flush=True)


def ask_ai(question: str) -> str:
    # 1. First try direct LLM if configured (fast and rich answers)
    if LLM_API_BASE_URL:
        try:
            req = urllib.request.Request(
                f"{LLM_API_BASE_URL.rstrip('/')}/chat/completions",
                data=json.dumps({
                    "model": LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": "คุณคือ AI ผู้ช่วยอัจฉริยะขององค์กร AItoB ตอบคำถามอย่างสุภาพ ถูกต้อง ชัดเจน และเป็นประโยชน์"},
                        {"role": "user", "content": question}
                    ],
                    "stream": False
                }).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {LLM_API_KEY}",
                    "User-Agent": "Mozilla/5.0"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.load(resp)
                choices = data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    if content:
                        return content
        except Exception as err:
            print(f"Direct LLM error: {err}", flush=True)

    # 2. Try AItoB Gateway (for internal docs & company workflows)
    try:
        req = urllib.request.Request(
            f"{GATEWAY_URL}/chat",
            data=json.dumps({"question": question}).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {AITOB_API_KEY}",
                "User-Agent": "Mozilla/5.0"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.load(resp)
            if "answer" in data:
                return data["answer"]
    except Exception as err:
        print(f"Gateway chat error: {err}", flush=True)

    return "ขออภัยครับ ขณะนี้ระบบประมวลผล AI ยังไม่พร้อมใช้งาน กรุณาลองใหม่อีกครั้ง"


class LineWebhookHandler(BaseHTTPRequestHandler):
    def reply_json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/health", "/"):
            self.reply_json(200, {"status": "ok", "service": "aitob-line-bot"})
            return
        self.reply_json(404, {"error": "not_found"})

    def do_POST(self):
        if self.path not in ("/webhook", "/line/webhook"):
            self.reply_json(404, {"error": "not_found"})
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        signature = self.headers.get("X-Line-Signature", "")

        # Verify signature if secret is configured
        if LINE_CHANNEL_SECRET and not verify_signature(LINE_CHANNEL_SECRET, body, signature):
            print("Invalid LINE signature", flush=True)
            self.reply_json(403, {"error": "invalid_signature"})
            return

        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            self.reply_json(400, {"error": "invalid_json"})
            return

        # Always return 200 OK immediately to satisfy LINE webhook verification
        self.reply_json(200, {"status": "received"})

        events = payload.get("events", [])
        for ev in events:
            if ev.get("type") == "message" and ev.get("message", {}).get("type") == "text":
                reply_token = ev.get("replyToken")
                user_msg = ev.get("message", {}).get("text", "").strip()
                user_id = ev.get("source", {}).get("userId", "")

                if not user_msg or not reply_token:
                    continue

                print(f"LINE Message received: {user_msg}", flush=True)
                show_loading(user_id, LINE_CHANNEL_ACCESS_TOKEN)
                answer = ask_ai(user_msg)
                print(f"AI Answer: {answer[:100]}...", flush=True)
                reply_line(reply_token, answer, LINE_CHANNEL_ACCESS_TOKEN)


def run_server():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), LineWebhookHandler)
    print(f"AItoB LINE Bot Service listening on port {PORT}...", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    run_server()

