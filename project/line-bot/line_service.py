import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DATA_DIR = Path(os.environ.get("LINE_DATA_DIR", "/home/aitob/data"))
INBOX_FILE = DATA_DIR / "inbox.json"
CONFIG_FILE = DATA_DIR / "line_config.json"
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

inbox_items = []


def load_data():
    global config, inbox_items
    # Load config
    for target in [CONFIG_FILE, Path("/tmp/line_config.json")]:
        if target.exists():
            try:
                with open(target, "r", encoding="utf-8") as f:
                    config.update(json.load(f))
                    break
            except Exception as e:
                print("Error loading config:", e, flush=True)

    # Load inbox
    for target in [INBOX_FILE, Path("/tmp/inbox.json")]:
        if target.exists():
            try:
                with open(target, "r", encoding="utf-8") as f:
                    inbox_items = json.load(f)
                    break
            except Exception as e:
                print("Error loading inbox:", e, flush=True)


def save_config(new_config: dict):
    global config
    for k in ("channel_secret", "channel_access_token", "llm_base_url", "llm_api_key", "llm_model"):
        if k in new_config and new_config[k] is not None:
            config[k] = str(new_config[k]).strip()

    for target in [CONFIG_FILE, Path("/tmp/line_config.json")]:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            pass
    return False


def save_inbox():
    for target in [INBOX_FILE, Path("/tmp/inbox.json")]:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                json.dump(inbox_items[:100], f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            pass
    return False


def get_line_profile(user_id: str, token: str) -> dict:
    if not token or not user_id:
        return {"displayName": "ผู้ใช้งาน LINE", "pictureUrl": ""}
    url = f"https://api.line.me/v2/bot/profile/{user_id}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "Mozilla/5.0"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.load(resp)
    except Exception:
        return {"displayName": "ผู้ใช้งาน LINE", "pictureUrl": ""}


def push_line_message(user_id: str, text: str, token: str):
    if not token or not user_id:
        print("Missing token or user_id for push, skipped", flush=True)
        return False
    url = "https://api.line.me/v2/bot/message/push"
    safe_text = text[:4900] if len(text) > 4900 else text
    payload = json.dumps({
        "to": user_id,
        "messages": [{"type": "text", "text": safe_text}]
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "Mozilla/5.0"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"Error pushing LINE message: {e}", flush=True)
        return False


def ask_ai(question: str, sender_name: str = "") -> str:
    system_prompt = (
        "คุณคือ AI ผู้ช่วยแอดมินตอบแชทขององค์กร AItoB\n"
        "หน้าที่ของคุณ: ร่างคำตอบที่ดีที่สุด สุภาพ กระชับ อ่านง่าย เหมาะกับการตอบในแชท LINE\n"
        "กฎสำคัญ:\n"
        "1. ตอบสั้นกระชับ 2-4 บรรทัด เว้นวรรคเป็นสัดส่วน ไม่ตอบเป็นก้อนตัวหนังสือยาว\n"
        "2. ใช้ภาษาพูดที่เป็นมิตรและเป็นมืออาชีพ มีหางเสียง (ครับ/ค่ะ)\n"
        "3. ถ้าเป็นคำทักทาย ให้ทักทายกลับอย่างอบอุ่นและสอบถามความต้องการ\n"
    )

    llm_url = config.get("llm_base_url")
    if llm_url:
        try:
            req = urllib.request.Request(
                f"{llm_url.rstrip('/')}/chat/completions",
                data=json.dumps({
                    "model": config.get("llm_model", "ag/gemini-3.8-flash-high"),
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"ข้อความจาก {sender_name or 'ลูกค้า'}: \"{question}\"\nช่วยร่างคำตอบที่ดีที่สุดให้หน่อย"}
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
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.load(resp)
                choices = data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    if content:
                        return content.strip()
        except Exception as err:
            print(f"Direct LLM error: {err}", flush=True)

    # Fallback default polite response
    return f"สวัสดีครับคุณ {sender_name or 'ลูกค้า'} 🙏 ขอบคุณที่ติดต่อเข้ามานะครับ ทางเราได้รับเรื่องเรียบร้อยแล้ว ยินดีดูแลและให้ข้อมูลเพิ่มเติมครับ"


def verify_signature(channel_secret: str, body: bytes, signature: str) -> bool:
    if not channel_secret or not signature:
        return False
    mac = hmac.new(channel_secret.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(mac).decode("utf-8")
    return hmac.compare_digest(expected, signature)


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AItoB - แดชบอร์ดช่วยตอบแชท (Smart Inbox)</title>
  <style>
    :root {
      --bg: #0b0f19;
      --card: #151d30;
      --card-border: #24304f;
      --text: #f8fafc;
      --muted: #94a3b8;
      --line: #06c755;
      --line-hover: #05b04c;
      --primary: #38bdf8;
      --danger: #ef4444;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Kanit', 'Segoe UI', Roboto, sans-serif; }
    body { background: var(--bg); color: var(--text); padding: 24px 16px; min-height: 100vh; display: flex; justify-content: center; }
    .container { max-width: 820px; width: 100%; }
    
    .navbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--card-border); }
    .logo { display: flex; align-items: center; gap: 10px; font-size: 20px; font-weight: 700; color: #fff; }
    .nav-actions { display: flex; gap: 10px; }
    
    .btn-sim { background: rgba(56, 189, 248, 0.15); color: var(--primary); border: 1px solid rgba(56, 189, 248, 0.4); padding: 8px 14px; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.2s; }
    .btn-sim:hover { background: rgba(56, 189, 248, 0.25); }
    .btn-cfg { background: #1e293b; color: #e2e8f0; border: 1px solid var(--card-border); padding: 8px 14px; border-radius: 8px; font-size: 13px; cursor: pointer; }
    
    .inbox-list { display: flex; flex-direction: column; gap: 20px; }
    
    .card { background: var(--card); border: 1px solid var(--card-border); border-radius: 16px; padding: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); transition: all 0.2s; }
    .card.sent { opacity: 0.65; border-color: rgba(6, 199, 85, 0.3); }
    
    .sender-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
    .sender-info { display: flex; align-items: center; gap: 12px; }
    .avatar { width: 42px; height: 42px; border-radius: 50%; background: #2563eb; color: #fff; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 16px; }
    .sender-name { font-size: 16px; font-weight: 600; color: #fff; }
    .msg-time { font-size: 12px; color: var(--muted); margin-top: 2px; }
    
    .badge { padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: 600; }
    .badge-pending { background: rgba(234, 179, 8, 0.15); color: #facc15; border: 1px solid rgba(234, 179, 8, 0.3); }
    .badge-sent { background: rgba(6, 199, 85, 0.15); color: #22c55e; border: 1px solid rgba(6, 199, 85, 0.3); }
    
    .section-title { font-size: 12.5px; font-weight: 600; color: var(--muted); margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px; display: flex; align-items: center; gap: 6px; }
    
    .question-box { background: #0c1222; border: 1px solid #1e2942; border-radius: 10px; padding: 12px 16px; font-size: 14.5px; color: #f1f5f9; margin-bottom: 16px; line-height: 1.5; border-left: 4px solid var(--primary); }
    
    .answer-wrapper { margin-bottom: 16px; }
    .answer-textarea {
      width: 100%; background: #090e1a; border: 1px solid #28375c; border-radius: 10px;
      padding: 14px; font-size: 14.5px; color: #fff; line-height: 1.6; resize: vertical; min-height: 100px;
      transition: all 0.2s;
    }
    .answer-textarea:focus { border-color: var(--line); outline: none; box-shadow: 0 0 0 3px rgba(6, 199, 85, 0.2); }
    
    .card-actions { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
    .btn-send {
      background: var(--line); color: #fff; border: none; padding: 10px 20px; border-radius: 9px;
      font-size: 14px; font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 8px; transition: all 0.2s;
    }
    .btn-send:hover { background: var(--line-hover); transform: translateY(-1px); }
    .btn-regen { background: #1e293b; color: #cbd5e1; border: 1px solid var(--card-border); padding: 10px 14px; border-radius: 9px; font-size: 13px; cursor: pointer; }
    .btn-regen:hover { background: #334155; }
    
    .empty-state { text-align: center; padding: 60px 20px; background: var(--card); border-radius: 16px; border: 1px dashed var(--card-border); }
    .empty-state h3 { font-size: 18px; margin-bottom: 8px; color: #fff; }
    .empty-state p { color: var(--muted); font-size: 14px; margin-bottom: 20px; }
    
    .toast { position: fixed; bottom: 24px; right: 24px; padding: 12px 20px; border-radius: 10px; background: #22c55e; color: #fff; font-size: 14px; font-weight: 600; display: none; box-shadow: 0 4px 15px rgba(0,0,0,0.4); z-index: 999; }
  </style>
</head>
<body>
  <div class="container">
    <div class="navbar">
      <div class="logo">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="#06c755"><path d="M12 2C6.48 2 2 5.92 2 10.75c0 3.03 1.77 5.71 4.5 7.22-.2 1.48-.72 3.41-1.63 4.48-.13.15-.02.39.18.39.98 0 3.32-.47 4.9-1.57.66.11 1.34.18 2.05.18 5.52 0 10-3.92 10-8.75S17.52 2 12 2z"/></svg>
        AItoB Smart Inbox
      </div>
      <div class="nav-actions">
        <button class="btn-sim" onclick="simulateMessage()">+ จำลองข้อความเข้าเพื่อทดสอบ</button>
      </div>
    </div>

    <div id="inboxContainer" class="inbox-list">
      <!-- Cards rendered here -->
    </div>
  </div>

  <div id="toast" class="toast">ส่งคำตอบเรียบร้อยแล้ว!</div>

  <script>
    let currentItems = [];

    async function loadInbox() {
      try {
        const res = await fetch("/api/inbox");
        if (res.ok) {
          const items = await res.json();
          currentItems = items;
          renderInbox(items);
        }
      } catch (e) {
        console.error("Load inbox error:", e);
      }
    }

    function renderInbox(items) {
      const container = document.getElementById("inboxContainer");
      if (!items || items.length === 0) {
        container.innerHTML = `
          <div class="empty-state">
            <h3>ยังไม่มีข้อความส่งเข้ามา</h3>
            <p>เมื่อมีคนส่งข้อความทาง LINE ข้อความและคำตอบที่ AI ช่วยร่างจะมาปรากฏที่นี่</p>
            <button class="btn-sim" onclick="simulateMessage()">กดที่นี่เพื่อทดสอบจำลองคำถาม</button>
          </div>
        `;
        return;
      }

      container.innerHTML = items.map(item => `
        <div class="card ${item.status === 'sent' ? 'sent' : ''}" id="card-${item.id}">
          <div class="sender-header">
            <div class="sender-info">
              <div class="avatar">${item.sender_name.slice(0, 1)}</div>
              <div>
                <div class="sender-name">${item.sender_name}</div>
                <div class="msg-time">${item.time}</div>
              </div>
            </div>
            <span class="badge ${item.status === 'sent' ? 'badge-sent' : 'badge-pending'}">
              ${item.status === 'sent' ? '✓ ส่งคำตอบแล้ว' : 'รอการตรวจสอบ'}
            </span>
          </div>

          <div class="section-title">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
            ข้อความที่พิมพ์ถามเข้ามา:
          </div>
          <div class="question-box">${escapeHtml(item.question)}</div>

          <div class="section-title">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a10 10 0 1 0 10 10H12V2z"/></svg>
            คำตอบที่ AI ช่วยร่างให้ (สามารถคลิกแก้ไขก่อนส่งได้):
          </div>
          <div class="answer-wrapper">
            <textarea class="answer-textarea" id="ans-${item.id}" ${item.status === 'sent' ? 'disabled' : ''}>${escapeHtml(item.ai_answer)}</textarea>
          </div>

          <div class="card-actions">
            <div>
              ${item.status !== 'sent' ? `
                <button class="btn-regen" onclick="regenerateAnswer('${item.id}')">🔄 ขอคำตอบใหม่</button>
              ` : `
                <span style="font-size: 13px; color: #22c55e;">ข้อความนี้ถูกส่งออกไปแล้ว</span>
              `}
            </div>
            ${item.status !== 'sent' ? `
              <button class="btn-send" onclick="sendReply('${item.id}')">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
                ยืนยันและส่งคำตอบเข้า LINE
              </button>
            ` : ''}
          </div>
        </div>
      `).join("");
    }

    async function sendReply(id) {
      const textarea = document.getElementById(`ans-${id}`);
      const text = textarea ? textarea.value.trim() : "";
      if (!text) {
        alert("กรุณากรอกข้อความก่อนส่ง");
        return;
      }

      try {
        const res = await fetch("/api/reply", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id, text })
        });
        if (res.ok) {
          showToast("ส่งคำตอบไปยัง LINE เรียบร้อยแล้ว!");
          loadInbox();
        } else {
          alert("ไม่สามารถส่งได้ กรุณาตรวจ Access Token");
        }
      } catch (err) {
        alert("ส่งไม่สำเร็จ: " + err);
      }
    }

    async function regenerateAnswer(id) {
      const item = currentItems.find(x => x.id === id);
      if (!item) return;
      const textarea = document.getElementById(`ans-${id}`);
      if (textarea) textarea.value = "กำลังคิดคำตอบใหม่...";
      
      try {
        const res = await fetch("/api/regenerate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id })
        });
        if (res.ok) {
          const data = await res.json();
          if (textarea) textarea.value = data.ai_answer;
        }
      } catch (e) {
        alert("ขอคำตอบใหม่ไม่สำเร็จ");
      }
    }

    async function simulateMessage() {
      const names = ["คุณสมชาย การค้า", "คุณแพรวา", "คุณณัฐพล", "คุณกิตติศักดิ์"];
      const questions = [
        "สวัสดีครับ ขอสอบถามหน่อยครับว่าระบบ AItoB ช่วยตรวจไฟล์ Excel อะไรได้บ้างครับ?",
        "ส่งเอกสารเบิกค่าใช้จ่ายประจำเดือนไปแล้ว ไม่ทราบว่าเช็คสถานะได้ที่ไหนคะ?",
        "ขอใบเสนอราคาแพ็กเกจสำหรับองค์กร 50 คนหน่อยครับ มีรายละเอียดอย่างไรบ้าง?"
      ];

      const sender = names[Math.floor(Math.random() * names.length)];
      const question = questions[Math.floor(Math.random() * questions.length)];

      try {
        await fetch("/api/simulate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sender_name: sender, question })
        });
        loadInbox();
      } catch (e) {
        console.error("Simulation error:", e);
      }
    }

    function showToast(msg) {
      const toast = document.getElementById("toast");
      toast.innerText = msg;
      toast.style.display = "block";
      setTimeout(() => { toast.style.display = "none"; }, 3000);
    }

    function escapeHtml(text) {
      const div = document.createElement("div");
      div.innerText = text;
      return div.innerHTML;
    }

    // Initial load and periodic refresh
    document.addEventListener("DOMContentLoaded", () => {
      loadInbox();
      setInterval(loadInbox, 5000);
    });
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

        if self.path == "/api/inbox":
            self.reply_json(200, inbox_items)
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

        if self.path in ("/", "/inbox", "/index.html"):
            body = DASHBOARD_HTML.encode("utf-8")
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

        # 1. Simulate incoming message
        if self.path == "/api/simulate":
            try:
                data = json.loads(body.decode("utf-8"))
                sender = data.get("sender_name", "คุณสมชาย")
                question = data.get("question", "สอบถามบริการครับ")
                
                ai_answer = ask_ai(question, sender)
                
                new_item = {
                    "id": str(uuid.uuid4())[:8],
                    "user_id": "simulated_user_1",
                    "sender_name": sender,
                    "question": question,
                    "ai_answer": ai_answer,
                    "status": "pending",
                    "time": time.strftime("%H:%M น.")
                }
                inbox_items.insert(0, new_item)
                save_inbox()
                self.reply_json(200, {"status": "ok", "item": new_item})
            except Exception as e:
                self.reply_json(400, {"error": str(e)})
            return

        # 2. Reply to a message (send to LINE)
        if self.path == "/api/reply":
            try:
                data = json.loads(body.decode("utf-8"))
                item_id = data.get("id")
                final_text = data.get("text", "")

                item = next((x for x in inbox_items if x["id"] == item_id), None)
                if not item:
                    self.reply_json(404, {"error": "item_not_found"})
                    return

                # Send out to LINE if real user_id
                user_id = item.get("user_id", "")
                token = config.get("channel_access_token", "")
                
                if not user_id.startswith("simulated_"):
                    push_line_message(user_id, final_text, token)

                item["ai_answer"] = final_text
                item["status"] = "sent"
                save_inbox()
                self.reply_json(200, {"status": "ok", "message": "sent"})
            except Exception as e:
                self.reply_json(400, {"error": str(e)})
            return

        # 3. Regenerate AI answer
        if self.path == "/api/regenerate":
            try:
                data = json.loads(body.decode("utf-8"))
                item_id = data.get("id")
                item = next((x for x in inbox_items if x["id"] == item_id), None)
                if not item:
                    self.reply_json(404, {"error": "item_not_found"})
                    return

                new_answer = ask_ai(item["question"], item["sender_name"])
                item["ai_answer"] = new_answer
                save_inbox()
                self.reply_json(200, {"status": "ok", "ai_answer": new_answer})
            except Exception as e:
                self.reply_json(400, {"error": str(e)})
            return

        # 4. Save settings
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

        # 5. LINE Webhook
        if self.path in ("/webhook", "/line/webhook"):
            signature = self.headers.get("X-Line-Signature", "")
            secret = config.get("channel_secret", "")

            if secret and not verify_signature(secret, body, signature):
                self.reply_json(403, {"error": "invalid_signature"})
                return

            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception:
                self.reply_json(400, {"error": "invalid_json"})
                return

            self.reply_json(200, {"status": "received"})

            events = payload.get("events", [])
            for ev in events:
                if ev.get("type") == "message" and ev.get("message", {}).get("type") == "text":
                    user_id = ev.get("source", {}).get("userId", "")
                    user_msg = ev.get("message", {}).get("text", "").strip()

                    if not user_msg:
                        continue

                    token = config.get("channel_access_token", "")
                    profile = get_line_profile(user_id, token)
                    sender_name = profile.get("displayName", "ผู้ใช้งาน LINE")

                    # Ask AI for best suggested answer
                    ai_answer = ask_ai(user_msg, sender_name)

                    new_item = {
                        "id": str(uuid.uuid4())[:8],
                        "user_id": user_id,
                        "sender_name": sender_name,
                        "question": user_msg,
                        "ai_answer": ai_answer,
                        "status": "pending",
                        "time": time.strftime("%H:%M น.")
                    }
                    inbox_items.insert(0, new_item)
                    save_inbox()
            return

        self.reply_json(404, {"error": "not_found"})


def run_server():
    load_data()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), LineWebhookHandler)
    print(f"AItoB Smart Inbox Service listening on port {PORT}...", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    run_server()
