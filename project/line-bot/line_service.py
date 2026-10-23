import base64
import hashlib
import hmac
import json
import os
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DATA_DIR = Path(os.environ.get("LINE_DATA_DIR", "/home/aitob/data"))
PORT = int(os.environ.get("LINE_BOT_PORT", "8003"))

# Runtime configuration store
config = {
    "channel_secret": os.environ.get("LINE_CHANNEL_SECRET", ""),
    "channel_access_token": os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", ""),
    "gateway_url": os.environ.get("GATEWAY_URL", "http://gateway:8000"),
    "aitob_api_key": os.environ.get("AITOB_API_KEY", ""),
    "llm_base_url": os.environ.get("LLM_API_BASE_URL", "https://rh7669c.abc-tunnel.us/v1"),
    "llm_api_key": os.environ.get("LLM_API_KEY", "sk-dec6393f10b69e7c-h0ukrj-57d33abf"),
    "llm_model": os.environ.get("LLM_MODEL", "ag/gemini-3.8-flash-high")
}


def load_config():
    global config
    candidates = [
        DATA_DIR / "line_config.json",
        Path("/tmp/line_config.json")
    ]
    for target in candidates:
        if target.exists():
            try:
                with open(target, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    config.update(saved)
                    print("Loaded configuration from", target, flush=True)
                    return
            except Exception as e:
                print(f"Error loading config from {target}: {e}", flush=True)


def save_config(new_config: dict):
    global config
    for k in ("channel_secret", "channel_access_token", "llm_base_url", "llm_api_key", "llm_model"):
        if k in new_config and new_config[k] is not None:
            config[k] = str(new_config[k]).strip()

    candidates = [
        DATA_DIR / "line_config.json",
        Path("/tmp/line_config.json")
    ]
    for target in candidates:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            print("Settings saved successfully to", target, flush=True)
            return True
        except Exception as e:
            print(f"Error saving config to {target}: {e}", flush=True)
    return False


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
        print("Missing LINE_CHANNEL_ACCESS_TOKEN or reply_token, skipping LINE reply", flush=True)
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
    # 1. Direct LLM via OpenAI-compatible endpoint
    llm_url = config.get("llm_base_url")
    if llm_url:
        try:
            req = urllib.request.Request(
                f"{llm_url.rstrip('/')}/chat/completions",
                data=json.dumps({
                    "model": config.get("llm_model", "ag/gemini-3.8-flash-high"),
                    "messages": [
                        {"role": "system", "content": "คุณคือ AI ผู้ช่วยอัจฉริยะขององค์กร AItoB ตอบคำถามอย่างสุภาพ ถูกต้อง ชัดเจน และเป็นประโยชน์"},
                        {"role": "user", "content": question}
                    ],
                    "stream": False
                }).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {config.get('llm_api_key', '')}",
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

    # 2. Fallback to Gateway
    gateway_url = config.get("gateway_url", "http://gateway:8000")
    try:
        req = urllib.request.Request(
            f"{gateway_url}/chat",
            data=json.dumps({"question": question}).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config.get('aitob_api_key', '')}",
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


WEB_PAGE_HTML = """<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AItoB - ตั้งค่า LINE Bot</title>
  <style>
    :root {
      --bg: #0f172a;
      --card: #1e293b;
      --border: #334155;
      --text: #f8fafc;
      --muted: #94a3b8;
      --primary: #06c755;
      --primary-hover: #05b04c;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Kanit', 'Segoe UI', Roboto, sans-serif; }
    body { background: var(--bg); color: var(--text); padding: 24px 16px; min-height: 100vh; display: flex; justify-content: center; }
    .container { max-width: 680px; width: 100%; }
    .header { text-align: center; margin-bottom: 24px; }
    .header h1 { font-size: 26px; font-weight: 700; color: #fff; display: flex; align-items: center; justify-content: center; gap: 10px; }
    .header p { color: var(--muted); font-size: 14px; margin-top: 6px; }
    .card { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 24px; margin-bottom: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); }
    .card h2 { font-size: 17px; font-weight: 600; margin-bottom: 16px; display: flex; align-items: center; justify-content: space-between; color: #fff; }
    .form-group { margin-bottom: 18px; }
    label { display: block; font-size: 13.5px; font-weight: 500; margin-bottom: 6px; color: #e2e8f0; }
    .desc { font-size: 12px; color: var(--muted); margin-bottom: 6px; }
    input[type="text"], input[type="password"], textarea {
      width: 100%; background: #0b1329; border: 1px solid var(--border); border-radius: 10px;
      padding: 10px 14px; font-size: 14px; color: #fff; transition: all 0.2s;
    }
    input:focus, textarea:focus { border-color: var(--primary); outline: none; box-shadow: 0 0 0 3px rgba(6, 199, 85, 0.2); }
    textarea { resize: vertical; min-height: 80px; font-family: monospace; font-size: 12px; }
    .btn {
      display: inline-flex; align-items: center; justify-content: center; width: 100%; padding: 12px 20px;
      font-size: 15px; font-weight: 600; border-radius: 10px; border: none; cursor: pointer; transition: all 0.2s;
      background: var(--primary); color: #fff;
    }
    .btn:hover { background: var(--primary-hover); transform: translateY(-1px); }
    .badge { display: inline-block; padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: 600; text-transform: uppercase; }
    .badge-ok { background: rgba(6, 199, 85, 0.15); color: #22c55e; border: 1px solid rgba(6, 199, 85, 0.3); }
    .badge-wait { background: rgba(234, 179, 8, 0.15); color: #eab308; border: 1px solid rgba(234, 179, 8, 0.3); }
    .info-box { background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 10px; padding: 14px; font-size: 13px; color: #bae6fd; line-height: 1.5; margin-bottom: 18px; }
    .info-box code { background: rgba(0,0,0,0.3); padding: 2px 6px; border-radius: 4px; font-family: monospace; }
    .toast { position: fixed; bottom: 24px; right: 24px; padding: 12px 20px; border-radius: 10px; background: #22c55e; color: #fff; font-size: 14px; font-weight: 500; display: none; box-shadow: 0 4px 15px rgba(0,0,0,0.4); }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>
        <svg width="28" height="28" viewBox="0 0 24 24" fill="#06c755"><path d="M12 2C6.48 2 2 5.92 2 10.75c0 3.03 1.77 5.71 4.5 7.22-.2 1.48-.72 3.41-1.63 4.48-.13.15-.02.39.18.39.98 0 3.32-.47 4.9-1.57.66.11 1.34.18 2.05.18 5.52 0 10-3.92 10-8.75S17.52 2 12 2z"/></svg>
        AItoB LINE Bot Settings
      </h1>
      <p>ตั้งค่า LINE Official Account เชื่อมโยงเข้ากับ AI Model องค์กร</p>
    </div>

    <div class="card">
      <h2>
        <span>1. ข้อมูลสำหรับ LINE Developers</span>
      </h2>
      <div class="info-box">
        นำ Webhook URL นี้ไปใส่ที่ <strong>LINE Developers Console &gt; Messaging API &gt; Webhook URL</strong> แล้วกด Verify พร้อมเปิด <strong>Use Webhook</strong>:<br>
        <div style="margin-top: 8px;">
          <code>https://&lt;your-tunnel-url&gt;/webhook</code>
        </div>
      </div>
    </div>

    <div class="card">
      <h2>
        <span>2. ตั้งค่า LINE Credentials</span>
        <span id="secretStatus" class="badge badge-wait">ยังไม่ได้กรอก</span>
      </h2>
      <div class="form-group">
        <label for="channelSecret">LINE Channel Secret</label>
        <div class="desc">คัดลอกจากแท็บ <strong>Basic settings</strong> ใน LINE Developers Console</div>
        <input type="password" id="channelSecret" placeholder="เช่น a1b2c3d4e5f6..." autocomplete="off">
      </div>

      <div class="form-group">
        <label for="channelAccessToken">LINE Channel Access Token (Long-lived)</label>
        <div class="desc">คัดลอกจากแท็บ <strong>Messaging API</strong> ใน LINE Developers Console</div>
        <textarea id="channelAccessToken" placeholder="เช่น eyJhbGciOiJIUzI1Ni..."></textarea>
      </div>
    </div>

    <div class="card">
      <h2>
        <span>3. AI Model ที่ใช้งาน</span>
      </h2>
      <div class="form-group">
        <label for="llmModel">ชื่อโมเดล (Model ID)</label>
        <input type="text" id="llmModel" value="ag/gemini-3.8-flash-high">
      </div>
      <div class="form-group">
        <label for="llmBaseUrl">OpenAI-Compatible Endpoint URL</label>
        <input type="text" id="llmBaseUrl" value="https://rh7669c.abc-tunnel.us/v1">
      </div>
      <div class="form-group">
        <label for="llmApiKey">API Key</label>
        <input type="password" id="llmApiKey" value="sk-dec6393f10b69e7c-h0ukrj-57d33abf">
      </div>

      <button class="btn" onclick="saveSettings()">บันทึกการตั้งค่า (Save Settings)</button>
    </div>
  </div>

  <div id="toast" class="toast">บันทึกการตั้งค่าเรียบร้อยแล้ว! พร้อมใช้งานทันที</div>

  <script>
    document.addEventListener("DOMContentLoaded", async () => {
      try {
        const res = await fetch("/api/settings");
        if (res.ok) {
          const data = await res.json();
          if (data.channel_secret) {
            document.getElementById("channelSecret").value = data.channel_secret;
            document.getElementById("secretStatus").className = "badge badge-ok";
            document.getElementById("secretStatus").innerText = "ตั้งค่าแล้ว";
          }
          if (data.channel_access_token) {
            document.getElementById("channelAccessToken").value = data.channel_access_token;
          }
          if (data.llm_model) document.getElementById("llmModel").value = data.llm_model;
          if (data.llm_base_url) document.getElementById("llmBaseUrl").value = data.llm_base_url;
          if (data.llm_api_key) document.getElementById("llmApiKey").value = data.llm_api_key;
        }
      } catch (e) {
        console.error("Failed to load settings:", e);
      }
    });

    async function saveSettings() {
      const payload = {
        channel_secret: document.getElementById("channelSecret").value.trim(),
        channel_access_token: document.getElementById("channelAccessToken").value.trim(),
        llm_model: document.getElementById("llmModel").value.trim(),
        llm_base_url: document.getElementById("llmBaseUrl").value.trim(),
        llm_api_key: document.getElementById("llmApiKey").value.trim()
      };

      try {
        const res = await fetch("/api/settings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });

        if (res.ok) {
          showToast("บันทึกการตั้งค่าเรียบร้อยแล้ว! พร้อมใช้งานทันที");
          if (payload.channel_secret) {
            document.getElementById("secretStatus").className = "badge badge-ok";
            document.getElementById("secretStatus").innerText = "ตั้งค่าแล้ว";
          }
        } else {
          alert("เกิดข้อผิดพลาดในการบันทึก");
        }
      } catch (err) {
        alert("บันทึกไม่สำเร็จ: " + err);
      }
    }

    function showToast(msg) {
      const toast = document.getElementById("toast");
      toast.innerText = msg;
      toast.style.display = "block";
      setTimeout(() => { toast.style.display = "none"; }, 3000);
    }
  </script>
</body>
</html>
"""


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
            return

        if self.path == "/api/settings":
            self.reply_json(200, {
                "channel_secret": config.get("channel_secret", ""),
                "channel_access_token": config.get("channel_access_token", ""),
                "llm_model": config.get("llm_model", "ag/gemini-3.8-flash-high"),
                "llm_base_url": config.get("llm_base_url", "https://rh7669c.abc-tunnel.us/v1"),
                "llm_api_key": config.get("llm_api_key", "")
            })
            return

        if self.path in ("/", "/settings", "/index.html"):
            body = WEB_PAGE_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.reply_json(404, {"error": "not_found"})

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        # 1. Update settings from Web UI
        if self.path == "/api/settings":
            try:
                new_data = json.loads(body.decode("utf-8"))
                if save_config(new_data):
                    self.reply_json(200, {"status": "ok", "message": "saved"})
                else:
                    self.reply_json(500, {"error": "save_failed"})
            except Exception as e:
                self.reply_json(400, {"error": str(e)})
            return

        # 2. LINE Webhook
        if self.path not in ("/webhook", "/line/webhook"):
            self.reply_json(404, {"error": "not_found"})
            return

        signature = self.headers.get("X-Line-Signature", "")
        secret = config.get("channel_secret", "")

        # Verify signature if secret is configured
        if secret and not verify_signature(secret, body, signature):
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

                token = config.get("channel_access_token", "")
                print(f"LINE Message received: {user_msg}", flush=True)
                show_loading(user_id, token)
                answer = ask_ai(user_msg)
                print(f"AI Answer: {answer[:100]}...", flush=True)
                reply_line(reply_token, answer, token)


def run_server():
    load_config()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), LineWebhookHandler)
    print(f"AItoB LINE Bot Service listening on port {PORT}...", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    run_server()
