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
    "llm_model": os.environ.get("LLM_MODEL", "ag/gemini-3.8-flash-high"),
    "auto_reply": False
}

inbox_items = []
recent_sends = {}



def load_data():
    global config, inbox_items
    for target in [CONFIG_FILE, Path("/tmp/line_config.json")]:
        if target.exists():
            try:
                with open(target, "r", encoding="utf-8") as f:
                    config.update(json.load(f))
                    break
            except Exception as e:
                print("Error loading config:", e, flush=True)

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
    for k in ("channel_secret", "channel_access_token", "llm_base_url", "llm_api_key", "llm_model", "auto_reply"):
        if k in new_config and new_config[k] is not None:
            config[k] = new_config[k]

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
                json.dump(inbox_items[:150], f, indent=2, ensure_ascii=False)
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


def reply_line_message(reply_token: str, text: str, token: str) -> bool:
    if not token or not reply_token:
        return False
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
            "Authorization": f"Bearer {token}",
            "User-Agent": "Mozilla/5.0"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"Reply token error (will try push): {e}", flush=True)
        return False


def push_line_message(user_id: str, text: str, token: str) -> bool:
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


def ask_ai(question: str, sender_name: str = "", tone: str = "balanced") -> str:
    tones = {
        "formal": "เน้นความเป็นทางการ สุภาพ เหมาะสำหรับลูกค้าองค์กร ข้อมูลครบถ้วนชัดเจน",
        "friendly": "เน้นความเป็นกันเอง สดใส สั้นกระชับ 1-3 บรรทัด มีอีโมจิประกอบ อ่านง่ายสบายตา",
        "balanced": "สุภาพ กระชับ อ่านง่าย 2-4 บรรทัด เว้นวรรคเป็นสัดส่วน มีหางเสียง (ครับ/ค่ะ)",
        "polite": "สุภาพ อ่อนน้อม ให้เกียรติลูกค้า มีหางเสียงครบถ้วน ใช้คำว่า ขออนุญาต/ยินดีให้บริการ",
        "concise": "สั้นกระชับ ตรงประเด็น ไม่เกิน 2 บรรทัด ตอบเฉพาะเนื้อหาสำคัญที่สุด"
    }
    tone_instruction = tones.get(tone, tones["balanced"])

    system_prompt = (
        "คุณคือ AI ผู้ช่วยแอดมินตอบแชทขององค์กร AItoB\n"
        f"หน้าที่ของคุณ: ร่างคำตอบที่ดีที่สุดสำหรับส่งกลับในแชท LINE โดย{tone_instruction}\n"
        "กฎสำคัญ:\n"
        "1. ตอบสั้นกระชับ ไม่ตอบเป็นก้อนข้อความยาวติดกัน\n"
        "2. ใช้ภาษาพูดที่เป็นธรรมชาติ ตอบตรงประเด็นคำถาม\n"
        "3. หากเป็นคำทักทาย ให้ทักทายกลับอย่างอบอุ่นและสอบถามความต้องการ\n"
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
                        {"role": "user", "content": f"ลูกค้าชื่อ: {sender_name or 'ลูกค้า'}\nข้อความที่ส่งมา: \"{question}\"\nช่วยร่างคำตอบที่ดีที่สุดให้หน่อย"}
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
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.load(resp)
                choices = data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    if content:
                        return content.strip()
        except Exception as err:
            print(f"Direct LLM error: {err}", flush=True)

    # Fallback default
    return f"สวัสดีครับคุณ {sender_name or 'ลูกค้า'} 🙏 ขอบคุณที่ติดต่อเข้ามานะครับ ทางเราได้รับเรื่องแล้ว ยินดีดูแลและให้ข้อมูลเพิ่มเติมครับ"


def verify_signature(channel_secret: str, body: bytes, signature: str) -> bool:
    if not channel_secret or not signature:
        return False
    mac = hmac.new(channel_secret.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(mac).decode("utf-8")
    return hmac.compare_digest(expected, signature)


def sync_to_webui(user_id: str, sender_name: str, question: str, ai_answer: str):
    try:
        req = urllib.request.Request(
            "http://webui:8080/api/internal/line-message",
            data=json.dumps({
                "user_id": user_id,
                "sender_name": sender_name,
                "question": question,
                "ai_answer": ai_answer
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            pass
    except Exception as e:
        print(f"Sync to Open WebUI failed: {e}", flush=True)


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AItoB - แดชบอร์ดตอบแชท LINE แบบ Real-time</title>
  <style>
    :root {
      --bg: #0b0f19;
      --card: #151d30;
      --card-border: #24304f;
      --card-highlight: #1e2c4c;
      --text: #f8fafc;
      --muted: #94a3b8;
      --line: #06c755;
      --line-hover: #05b04c;
      --line-light: rgba(6, 199, 85, 0.15);
      --primary: #38bdf8;
      --primary-light: rgba(56, 189, 248, 0.15);
      --warning: #f59e0b;
      --warning-light: rgba(245, 158, 11, 0.15);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Kanit', 'Segoe UI', Roboto, sans-serif; }
    body { background: var(--bg); color: var(--text); padding: 24px 16px; min-height: 100vh; display: flex; justify-content: center; }
    .container { max-width: 860px; width: 100%; }

    /* Header & Bar */
    .navbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 16px; border-bottom: 1px solid var(--card-border); }
    .logo-area { display: flex; align-items: center; gap: 12px; }
    .logo-title { font-size: 20px; font-weight: 700; color: #fff; display: flex; align-items: center; gap: 8px; }
    .status-pill { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; padding: 3px 10px; border-radius: 20px; background: rgba(6, 199, 85, 0.12); color: #22c55e; border: 1px solid rgba(6, 199, 85, 0.3); }
    .status-dot { width: 8px; height: 8px; border-radius: 50%; background: #22c55e; animation: pulse 2s infinite; }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

    .nav-actions { display: flex; gap: 8px; align-items: center; }
    .btn-notif { background: #1e293b; color: #cbd5e1; border: 1px solid var(--card-border); padding: 7px 12px; border-radius: 8px; font-size: 13px; font-weight: 500; cursor: pointer; display: flex; align-items: center; gap: 6px; transition: all 0.2s; }
    .btn-notif:hover { background: #334155; color: #fff; }
    .btn-notif.active { background: rgba(6, 199, 85, 0.2); color: #22c55e; border-color: rgba(6, 199, 85, 0.4); }

    .btn-sim { background: var(--primary-light); color: var(--primary); border: 1px solid rgba(56, 189, 248, 0.4); padding: 7px 14px; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.2s; }
    .btn-sim:hover { background: rgba(56, 189, 248, 0.28); transform: translateY(-1px); }

    /* Filter Bar */
    .filter-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
    .tabs { display: flex; gap: 8px; }
    .tab-btn { background: transparent; border: 1px solid transparent; color: var(--muted); padding: 6px 14px; border-radius: 8px; font-size: 13px; font-weight: 500; cursor: pointer; transition: all 0.2s; }
    .tab-btn:hover { color: #fff; background: rgba(255, 255, 255, 0.05); }
    .tab-btn.active { background: var(--card); border-color: var(--card-border); color: #fff; font-weight: 600; }
    .badge-count { background: #ef4444; color: #fff; font-size: 11px; padding: 2px 7px; border-radius: 10px; margin-left: 5px; font-weight: 700; }

    /* Notification Alert Banner */
    .notif-banner { background: #172554; border: 1px solid #1e40af; border-radius: 12px; padding: 12px 16px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; font-size: 13.5px; color: #bfdbfe; }
    .notif-banner button { background: #3b82f6; color: #fff; border: none; padding: 6px 14px; border-radius: 6px; font-size: 12.5px; font-weight: 600; cursor: pointer; }

    /* Inbox List */
    .inbox-list { display: flex; flex-direction: column; gap: 20px; }

    .card { background: var(--card); border: 1px solid var(--card-border); border-radius: 16px; padding: 22px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); transition: all 0.25s; position: relative; }
    .card.new-alert { animation: glow 1.5s ease-in-out 3; border-color: var(--line); }
    @keyframes glow { 0%, 100% { box-shadow: 0 0 0 1px var(--card-border); } 50% { box-shadow: 0 0 25px rgba(6, 199, 85, 0.45); } }
    .card.sent { opacity: 0.72; border-color: rgba(6, 199, 85, 0.3); }

    .card-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
    .sender-group { display: flex; align-items: center; gap: 12px; }
    .avatar-img { width: 44px; height: 44px; border-radius: 50%; object-fit: cover; border: 2px solid #24304f; }
    .avatar-fallback { width: 44px; height: 44px; border-radius: 50%; background: linear-gradient(135deg, #0284c7, #2563eb); color: #fff; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 17px; }
    .sender-details { display: flex; flex-direction: column; }
    .sender-name { font-size: 16px; font-weight: 600; color: #fff; display: flex; align-items: center; gap: 6px; }
    .sender-time { font-size: 12px; color: var(--muted); margin-top: 2px; }

    .badge-status { padding: 4px 10px; border-radius: 6px; font-size: 11.5px; font-weight: 600; display: inline-flex; align-items: center; gap: 5px; }
    .badge-pending { background: var(--warning-light); color: #facc15; border: 1px solid rgba(245, 158, 11, 0.3); }
    .badge-sent { background: var(--line-light); color: #22c55e; border: 1px solid rgba(6, 199, 85, 0.3); }

    .field-label { font-size: 12px; font-weight: 600; color: var(--muted); margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px; display: flex; justify-content: space-between; align-items: center; }
    .field-label span { display: flex; align-items: center; gap: 5px; }

    .question-box { background: #0c1222; border: 1px solid #1e2942; border-radius: 10px; padding: 14px 16px; font-size: 15px; color: #f1f5f9; margin-bottom: 16px; line-height: 1.55; border-left: 4px solid var(--primary); }

    .tone-buttons { display: flex; gap: 6px; margin-bottom: 8px; }
    .btn-tone { background: #1e293b; color: #94a3b8; border: 1px solid var(--card-border); padding: 4px 10px; border-radius: 6px; font-size: 11.5px; cursor: pointer; transition: all 0.2s; }
    .btn-tone:hover { background: #334155; color: #fff; }

    .answer-textarea {
      width: 100%; background: #090e1a; border: 1px solid #28375c; border-radius: 10px;
      padding: 14px; font-size: 14.5px; color: #fff; line-height: 1.6; resize: vertical; min-height: 95px;
      transition: all 0.2s; margin-bottom: 16px;
    }
    .answer-textarea:focus { border-color: var(--line); outline: none; box-shadow: 0 0 0 3px rgba(6, 199, 85, 0.2); }

    .card-footer { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
    .footer-left { display: flex; gap: 8px; align-items: center; }
    .btn-action-sec { background: #1e293b; color: #cbd5e1; border: 1px solid var(--card-border); padding: 8px 12px; border-radius: 8px; font-size: 12.5px; cursor: pointer; transition: all 0.2s; }
    .btn-action-sec:hover { background: #334155; color: #fff; }

    .btn-send-main {
      background: var(--line); color: #fff; border: none; padding: 10px 22px; border-radius: 9px;
      font-size: 14.5px; font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 8px; transition: all 0.2s;
    }
    .btn-send-main:hover { background: var(--line-hover); transform: translateY(-1px); box-shadow: 0 4px 12px rgba(6, 199, 85, 0.35); }
    .btn-send-main:disabled { background: #334155; color: #94a3b8; cursor: not-allowed; transform: none; box-shadow: none; }

    .empty-state { text-align: center; padding: 60px 20px; background: var(--card); border-radius: 16px; border: 1px dashed var(--card-border); }
    .empty-state h3 { font-size: 18px; margin-bottom: 8px; color: #fff; }
    .empty-state p { color: var(--muted); font-size: 14px; margin-bottom: 20px; }

    .toast { position: fixed; bottom: 24px; right: 24px; padding: 12px 22px; border-radius: 10px; background: #22c55e; color: #fff; font-size: 14px; font-weight: 600; display: none; box-shadow: 0 6px 20px rgba(0,0,0,0.4); z-index: 999; animation: slideUp 0.3s; }
    @keyframes slideUp { from { transform: translateY(20px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
  </style>
</head>
<body>
  <div class="container">
    <!-- Navbar -->
    <div class="navbar">
      <div class="logo-area">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="#06c755"><path d="M12 2C6.48 2 2 5.92 2 10.75c0 3.03 1.77 5.71 4.5 7.22-.2 1.48-.72 3.41-1.63 4.48-.13.15-.02.39.18.39.98 0 3.32-.47 4.9-1.57.66.11 1.34.18 2.05.18 5.52 0 10-3.92 10-8.75S17.52 2 12 2z"/></svg>
        <div>
          <div class="logo-title">
            AItoB Smart Inbox
            <span class="status-pill"><span class="status-dot"></span> เชื่อมต่อพร้อมทำงาน</span>
          </div>
        </div>
      </div>
      <div class="nav-actions">
        <a href="/" target="_top" style="text-decoration: none; color: #cbd5e1; font-size: 13px; background: #1e293b; padding: 7px 12px; border-radius: 8px; border: 1px solid var(--card-border); display: flex; align-items: center; gap: 6px;">
          💬 กลับหน้าแชท Open WebUI
        </a>
        <label style="display: flex; align-items: center; gap: 7px; font-size: 13px; color: #cbd5e1; cursor: pointer; background: #1e293b; padding: 7px 12px; border-radius: 8px; border: 1px solid var(--card-border);">
          <input type="checkbox" id="autoReplyToggle" name="autoReplyToggle" onchange="toggleAutoReply(this.checked)" style="accent-color: #06c755; cursor: pointer; width: 16px; height: 16px;">
          <span>ตอบอัตโนมัติ (Auto-Reply)</span>
        </label>
        <button id="btnNotifToggle" class="btn-notif" onclick="toggleNotifications()">
          🔔 เปิดเสียง & แจ้งเตือน
        </button>
        <button class="btn-sim" onclick="simulateMessage()">+ จำลองข้อความเข้าเพื่อทดสอบ</button>
      </div>
    </div>

    <!-- Notification Permission Banner (if not granted) -->
    <div id="notifBanner" class="notif-banner" style="display: none;">
      <div>
        <strong>🔔 แนะนำให้เปิดแจ้งเตือน:</strong> เพื่อให้หน้าจอดังเสียง "ติ๊ง!" และเด้งป๊อปอัปแจ้งเตือนทันทีที่มีลูกค้าทัก LINE เข้ามา
      </div>
      <button onclick="requestNotificationAccess()">กดอนุญาตแจ้งเตือน</button>
    </div>

    <!-- Filter Bar -->
    <div class="filter-bar">
      <div class="tabs">
        <button class="tab-btn active" id="tabAll" onclick="setFilter('all')">ทั้งหมด</button>
        <button class="tab-btn" id="tabPending" onclick="setFilter('pending')">
          🟡 รอตรวจสอบและส่ง <span id="pendingBadge" class="badge-count" style="display: none;">0</span>
        </button>
        <button class="tab-btn" id="tabSent" onclick="setFilter('sent')">🟢 ส่งตอบแล้ว</button>
      </div>
      <div style="font-size: 12.5px; color: var(--muted);" id="syncStatus">
        ตรวจสอบข้อความใหม่อัตโนมัติทุก 2 วินาที
      </div>
    </div>

    <!-- Inbox List Container -->
    <div id="inboxContainer" class="inbox-list"></div>
  </div>

  <div id="toast" class="toast">ส่งคำตอบเรียบร้อยแล้ว!</div>

  <script>
    let currentItems = [];
    let knownIds = new Set();
    let currentFilter = 'all';
    let soundEnabled = true;
    let audioUnlocked = false;

    // Web Audio Chime (crisp two-tone chime without external file dependencies)
    function playChime() {
      if (!soundEnabled) return;
      try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        const ctx = new AudioContext();
        
        // Tone 1: D5 (587.33 Hz)
        const osc1 = ctx.createOscillator();
        const gain1 = ctx.createGain();
        osc1.type = "sine";
        osc1.frequency.setValueAtTime(587.33, ctx.currentTime);
        gain1.gain.setValueAtTime(0.2, ctx.currentTime);
        gain1.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
        osc1.connect(gain1);
        gain1.connect(ctx.destination);
        osc1.start();
        osc1.stop(ctx.currentTime + 0.35);

        // Tone 2: A5 (880 Hz) - delayed 0.12s
        const osc2 = ctx.createOscillator();
        const gain2 = ctx.createGain();
        osc2.type = "sine";
        osc2.frequency.setValueAtTime(880, ctx.currentTime + 0.12);
        gain2.gain.setValueAtTime(0.25, ctx.currentTime + 0.12);
        gain2.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.55);
        osc2.connect(gain2);
        gain2.connect(ctx.destination);
        osc2.start(ctx.currentTime + 0.12);
        osc2.stop(ctx.currentTime + 0.6);
      } catch (e) {
        console.log("Audio play error", e);
      }
    }

    function checkNotificationStatus() {
      if (!("Notification" in window)) return;
      const banner = document.getElementById("notifBanner");
      const btn = document.getElementById("btnNotifToggle");
      if (Notification.permission === "granted") {
        banner.style.display = "none";
        btn.classList.add("active");
        btn.innerHTML = "🔔 แจ้งเตือนเปิดอยู่ (เสียงดัง)";
      } else if (Notification.permission === "default") {
        banner.style.display = "flex";
        btn.innerHTML = "🔔 เปิดเสียง & แจ้งเตือน";
      } else {
        banner.style.display = "none";
        btn.innerHTML = "🔕 การแจ้งเตือนถูกปิดกั้น";
      }
    }

    async function requestNotificationAccess() {
      if (!("Notification" in window)) return;
      const res = await Notification.requestPermission();
      checkNotificationStatus();
      if (res === "granted") {
        playChime();
        showToast("เปิดระบบแจ้งเตือนและเสียงเตือนเรียบร้อยแล้ว!");
      }
    }

    function toggleNotifications() {
      if (Notification.permission !== "granted") {
        requestNotificationAccess();
      } else {
        soundEnabled = !soundEnabled;
        const btn = document.getElementById("btnNotifToggle");
        if (soundEnabled) {
          btn.classList.add("active");
          btn.innerHTML = "🔔 แจ้งเตือนเปิดอยู่ (เสียงดัง)";
          playChime();
        } else {
          btn.classList.remove("active");
          btn.innerHTML = "🔕 ปิดเสียงแจ้งเตือนแล้ว";
        }
      }
    }

    function showDesktopPopup(sender, message, itemId) {
      if ("Notification" in window && Notification.permission === "granted") {
        try {
          const notif = new Notification(`💬 ข้อความใหม่จาก LINE: ${sender}`, {
            body: message,
            icon: "https://vos.line-scdn.net/service-notifier/line_logo.png"
          });
          notif.onclick = () => {
            window.focus();
            const el = document.getElementById(`card-${itemId}`);
            if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
          };
        } catch (e) {
          console.error("Popup error:", e);
        }
      }
    }

    async function loadInbox() {
      try {
        const res = await fetch("/api/inbox");
        if (!res.ok) return;
        const items = await res.json();

        // Check for new incoming items
        let hasNew = false;
        items.forEach(it => {
          if (!knownIds.has(it.id)) {
            knownIds.add(it.id);
            if (it.status === 'pending') {
              hasNew = true;
              showDesktopPopup(it.sender_name, it.question, it.id);
            }
          }
        });

        if (hasNew) {
          playChime();
        }

        currentItems = items;
        updateBadgeAndTitle();
        renderInbox();
      } catch (e) {
        console.error("Load inbox error:", e);
      }
    }

    function updateBadgeAndTitle() {
      const pendingCount = currentItems.filter(x => x.status !== 'sent').length;
      const badge = document.getElementById("pendingBadge");
      if (pendingCount > 0) {
        badge.innerText = pendingCount;
        badge.style.display = "inline";
        document.title = `🔴 (${pendingCount}) มีข้อความใหม่จาก LINE! - AItoB Smart Inbox`;
      } else {
        badge.style.display = "none";
        document.title = "AItoB - แดชบอร์ดตอบแชท LINE แบบ Real-time";
      }
    }

    function setFilter(filter) {
      currentFilter = filter;
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      if (filter === 'all') document.getElementById("tabAll").classList.add("active");
      if (filter === 'pending') document.getElementById("tabPending").classList.add("active");
      if (filter === 'sent') document.getElementById("tabSent").classList.add("active");
      renderInbox();
    }

    function renderInbox() {
      const container = document.getElementById("inboxContainer");
      let items = currentItems;
      if (currentFilter === 'pending') {
        items = currentItems.filter(x => x.status !== 'sent');
      } else if (currentFilter === 'sent') {
        items = currentItems.filter(x => x.status === 'sent');
      }

      if (!items || items.length === 0) {
        container.innerHTML = `
          <div class="empty-state">
            <h3>ยังไม่มีข้อความในหมวดนี้</h3>
            <p>เมื่อลูกค้าส่งข้อความทาง LINE ข้อความพร้อมคำตอบที่ AI ช่วยคิดจะแสดงที่นี่แบบสดๆ ทันที</p>
            <button class="btn-sim" onclick="simulateMessage()">กดที่นี่เพื่อทดสอบจำลองข้อความเข้า</button>
          </div>
        `;
        return;
      }

      container.innerHTML = items.map(item => `
        <div class="card ${item.status === 'sent' ? 'sent' : 'new-alert'}" id="card-${item.id}">
          <div class="card-top">
            <div class="sender-group">
              ${item.picture_url ? 
                `<img class="avatar-img" src="${escapeHtml(item.picture_url)}" alt="avatar">` : 
                `<div class="avatar-fallback">${escapeHtml(item.sender_name.slice(0, 1))}</div>`
              }
              <div class="sender-details">
                <div class="sender-name">
                  ${escapeHtml(item.sender_name)}
                  <span style="font-size: 11px; color: #22c55e;">● LINE Official</span>
                </div>
                <div class="sender-time">ได้รับเมื่อเวลา ${escapeHtml(item.time)}</div>
              </div>
            </div>
            <span class="badge-status ${item.status === 'sent' ? 'badge-sent' : 'badge-pending'}">
              ${item.auto_replied ? '🤖 AI ตอบอัตโนมัติแล้ว' : (item.status === 'sent' ? '✓ ส่งคำตอบถึงลูกค้าแล้ว' : '🟡 รอคุณตรวจสอบและส่ง')}
            </span>
          </div>

          <div class="field-label">
            <span>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
              ข้อความที่ลูกค้าพิมพ์ถามเข้ามา:
            </span>
          </div>
          <div class="question-box">${escapeHtml(item.question)}</div>

          <div class="field-label">
            <span>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a10 10 0 1 0 10 10H12V2z"/></svg>
              คำตอบที่ดีที่สุดที่ AI ช่วยร่างให้ (สามารถคลิกแก้ไขข้อความได้โดยตรง):
            </span>
            ${item.status !== 'sent' ? `
              <div class="tone-buttons">
                <button class="btn-tone" onclick="rewriteTone('${item.id}', 'formal')">👔 เป็นทางการ</button>
                <button class="btn-tone" onclick="rewriteTone('${item.id}', 'friendly')">😊 เป็นกันเอง</button>
              </div>
            ` : ''}
          </div>
          <textarea class="answer-textarea" id="ans-${item.id}" name="ans-${item.id}" ${item.status === 'sent' ? 'disabled' : ''}>${escapeHtml(item.ai_answer)}</textarea>

          <div class="card-footer">
            <div class="footer-left">
              ${item.status !== 'sent' ? `
                <button class="btn-action-sec" onclick="regenerateAnswer('${item.id}')">🔄 ขอคำตอบใหม่</button>
              ` : `
                <span style="font-size: 13px; color: #22c55e;">ข้อความนี้ส่งกลับเข้า LINE ลูกค้าเรียบร้อยแล้ว</span>
              `}
              <button class="btn-action-sec" style="color: #ef4444;" onclick="deleteItem('${item.id}')">ลบ</button>
            </div>
            ${item.status !== 'sent' ? `
              <button class="btn-send-main" id="btn-send-${item.id}" onclick="sendReply('${item.id}')">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
                ยืนยันและส่งเข้า LINE ทันที
              </button>
            ` : ''}
          </div>
        </div>
      `).join("");
    }

    async function sendReply(id) {
      const textarea = document.getElementById(`ans-${id}`);
      const btn = document.getElementById(`btn-send-${id}`);
      const text = textarea ? textarea.value.trim() : "";
      if (!text) {
        alert("กรุณากรอกข้อความก่อนส่ง");
        return;
      }

      if (btn) {
        btn.disabled = true;
        btn.innerText = "กำลังส่งข้อความ...";
      }

      try {
        const res = await fetch("/api/reply", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id, text })
        });
        if (res.ok) {
          showToast("✓ ส่งคำตอบกลับไปยัง LINE ของลูกค้าเรียบร้อยแล้ว!");
          loadInbox();
        } else {
          alert("ไม่สามารถส่งได้ กรุณาตรวจสอบว่าใส่ LINE Channel Access Token แล้วหรือยัง");
          if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg> ยืนยันและส่งเข้า LINE ทันที`;
          }
        }
      } catch (err) {
        alert("ส่งไม่สำเร็จ: " + err);
        if (btn) btn.disabled = false;
      }
    }

    async function regenerateAnswer(id) {
      const textarea = document.getElementById(`ans-${id}`);
      if (textarea) textarea.value = "🤖 กำลังคิดคำตอบใหม่ให้เหมาะสมที่สุด...";
      try {
        const res = await fetch("/api/regenerate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id, tone: 'balanced' })
        });
        if (res.ok) {
          const data = await res.json();
          if (textarea) textarea.value = data.ai_answer;
        }
      } catch (e) {
        alert("ขอคำตอบใหม่ไม่สำเร็จ");
      }
    }

    async function rewriteTone(id, tone) {
      const textarea = document.getElementById(`ans-${id}`);
      if (textarea) textarea.value = `🤖 กำลังปรับสำนวนให้ (${tone === 'formal' ? 'ทางการ' : 'เป็นกันเอง'})...`;
      try {
        const res = await fetch("/api/regenerate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id, tone })
        });
        if (res.ok) {
          const data = await res.json();
          if (textarea) textarea.value = data.ai_answer;
        }
      } catch (e) {
        alert("ปรับสำนวนไม่สำเร็จ");
      }
    }

    async function deleteItem(id) {
      if (!confirm("ต้องการลบรายการนี้ใช่หรือไม่?")) return;
      try {
        await fetch("/api/delete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id })
        });
        currentItems = currentItems.filter(x => x.id !== id);
        updateBadgeAndTitle();
        renderInbox();
      } catch (e) {}
    }

    async function simulateMessage() {
      const sampleSenders = [
        { name: "คุณกิตติศักดิ์ พัฒนา", pic: "" },
        { name: "คุณพรทิพย์ สุวรรณ", pic: "" },
        { name: "คุณอนันต์ บริการ", pic: "" },
        { name: "คุณมินตรา ธุรกิจ", pic: "" }
      ];
      const sampleQuestions = [
        "สวัสดีครับ ขอสอบถามหน่อยครับว่าระบบ AItoB รองรับการเชื่อมต่อกับระบบสต็อกสินค้าไหมครับ?",
        "ส่งเอกสารขอเคลมสินค้าไปเมื่อวานนี้ อยากทราบว่าต้องรอประมาณกี่วันทำการคะ?",
        "ถ้าต้องการสมัครแพ็กเกจองค์กรสำหรับ 20 ท่าน มีส่วนลดพิเศษไหมครับ และขอใบเสนอราคาได้ทางไหน?",
        "สวัสดีค่ะ สนใจให้ทางทีมเข้ามาแนะนำการใช้งานระบบ มีค่าใช้จ่ายไหมคะ?"
      ];

      const s = sampleSenders[Math.floor(Math.random() * sampleSenders.length)];
      const q = sampleQuestions[Math.floor(Math.random() * sampleQuestions.length)];

      try {
        await fetch("/api/simulate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sender_name: s.name, question: q, picture_url: s.pic })
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
      setTimeout(() => { toast.style.display = "none"; }, 3500);
    }

    function escapeHtml(text) {
      if (!text) return "";
      const div = document.createElement("div");
      div.innerText = text;
      return div.innerHTML;
    }

    async function loadSettings() {
      try {
        const res = await fetch("/api/settings");
        if (res.ok) {
          const s = await res.json();
          const toggle = document.getElementById("autoReplyToggle");
          if (toggle) toggle.checked = !!s.auto_reply;
        }
      } catch (e) {}
    }

    async function toggleAutoReply(enabled) {
      try {
        const res = await fetch("/api/settings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ auto_reply: enabled })
        });
        if (res.ok) {
          showToast(enabled ? "✓ เปิดโหมด: AI ตอบกลับข้อความใน LINE ทันทีอัตโนมัติ" : "เปิดโหมด: ให้แอดมินตรวจและกดส่งเอง");
        }
      } catch (e) {
        alert("บันทึกการตั้งค่าไม่สำเร็จ");
      }
    }

    document.addEventListener("DOMContentLoaded", () => {
      checkNotificationStatus();
      loadSettings();
      loadInbox();
      // Fast polling every 2.5 seconds for instant real-time response
      setInterval(loadInbox, 2500);

      // Unlock Web Audio on first user interaction anywhere
      window.addEventListener("click", () => {
        if (!audioUnlocked) {
          try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            ctx.resume();
            audioUnlocked = true;
          } catch (e) {}
        }
      }, { once: true });
    });
  </script>
</body>
</html>
"""


class LineWebhookHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

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
                "llm_api_key": config.get("llm_api_key", ""),
                "auto_reply": bool(config.get("auto_reply", False))
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
        global inbox_items
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        # 1. Simulate incoming message
        if self.path == "/api/simulate":
            try:
                data = json.loads(body.decode("utf-8"))
                sender = data.get("sender_name", "คุณลูกค้า")
                question = data.get("question", "สอบถามบริการครับ")
                pic = data.get("picture_url", "")
                
                ai_answer = ask_ai(question, sender, "balanced")
                
                new_item = {
                    "id": str(uuid.uuid4())[:8],
                    "user_id": "simulated_user_" + str(uuid.uuid4())[:4],
                    "reply_token": "",
                    "reply_token_time": time.time(),
                    "sender_name": sender,
                    "picture_url": pic,
                    "question": question,
                    "ai_answer": ai_answer,
                    "status": "pending",
                    "time": time.strftime("%H:%M น.")
                }
                inbox_items.insert(0, new_item)
                save_inbox()
                sync_to_webui(new_item["user_id"], sender, question, ai_answer)
                self.reply_json(200, {"status": "ok", "item": new_item})
            except Exception as e:
                self.reply_json(400, {"error": str(e)})
            return

        # 2. Reply to a message (send to LINE)
        if self.path == "/api/reply":
            try:
                data = json.loads(body.decode("utf-8"))
                item_id = data.get("id")
                final_text = (data.get("text", "") or data.get("message", "")).strip()
                target_user_id = data.get("user_id")

                now_ts = time.time()
                send_key = f"{target_user_id}:{hashlib.md5(final_text.encode('utf-8')).hexdigest()}"
                if send_key in recent_sends and (now_ts - recent_sends[send_key]) < 3.0:
                    self.reply_json(200, {"status": "ok", "delivered": True, "duplicate_prevented": True})
                    return
                recent_sends[send_key] = now_ts

                token = config.get("channel_access_token", "")

                if target_user_id and not item_id:
                    delivered = True if target_user_id.startswith("simulated_") else push_line_message(target_user_id, final_text, token)
                    self.reply_json(200, {"status": "ok", "delivered": delivered})
                    return

                item = next((x for x in inbox_items if x["id"] == item_id), None)
                if not item:
                    # Try finding by user_id
                    item = next((x for x in inbox_items if x.get("user_id") == target_user_id), None)

                if not item:
                    if target_user_id:
                        delivered = True if target_user_id.startswith("simulated_") else push_line_message(target_user_id, final_text, token)
                        self.reply_json(200, {"status": "ok", "delivered": delivered})
                        return
                    self.reply_json(404, {"error": "item_not_found"})
                    return

                user_id = item.get("user_id", "") or target_user_id
                reply_token = item.get("reply_token", "")
                reply_token_time = item.get("reply_token_time", 0)

                delivered = False
                if not user_id.startswith("simulated_"):
                    # Attempt replyToken if under 50 seconds
                    if reply_token and (time.time() - reply_token_time) < 50:
                        delivered = reply_line_message(reply_token, final_text, token)

                    # Fallback to pushMessage
                    if not delivered:
                        delivered = push_line_message(user_id, final_text, token)
                else:
                    delivered = True

                item["ai_answer"] = final_text
                item["status"] = "sent" if delivered else "failed"
                save_inbox()
                if not delivered:
                    self.reply_json(500, {"error": "delivery_failed", "message": "ส่งเข้า LINE ไม่สำเร็จ กรุณาตรวจ Channel Access Token"})
                    return
                self.reply_json(200, {"status": "ok", "message": "sent", "delivered": delivered})
            except Exception as e:
                self.reply_json(400, {"error": str(e)})
            return

        # 2.2 Update message status (e.g. cancelled, edited, pending_review)
        if self.path == "/api/update-status":
            try:
                data = json.loads(body.decode("utf-8"))
                item_id = data.get("id")
                new_status = data.get("status")
                new_text = data.get("text")
                item = next((x for x in inbox_items if x["id"] == item_id), None)
                if item:
                    if new_status:
                        item["status"] = new_status
                    if new_text:
                        item["ai_answer"] = new_text
                    save_inbox()
                    self.reply_json(200, {"status": "ok", "item": item})
                    return
                self.reply_json(404, {"error": "item_not_found"})
            except Exception as e:
                self.reply_json(400, {"error": str(e)})
            return

        # 2.5 Ask AI draft
        if self.path == "/api/ask-ai":
            try:
                data = json.loads(body.decode("utf-8"))
                q = data.get("question", "")
                sender = data.get("sender_name", "ลูกค้า")
                tone = data.get("tone", "balanced")
                ans = ask_ai(q, sender, tone)
                self.reply_json(200, {"status": "ok", "answer": ans})
            except Exception as e:
                self.reply_json(400, {"error": str(e)})
            return

        # 3. Regenerate AI answer (with tone)
        if self.path == "/api/regenerate":
            try:
                data = json.loads(body.decode("utf-8"))
                item_id = data.get("id")
                tone = data.get("tone", "balanced")
                item = next((x for x in inbox_items if x["id"] == item_id), None)
                if not item:
                    self.reply_json(404, {"error": "item_not_found"})
                    return

                new_answer = ask_ai(item["question"], item["sender_name"], tone)
                item["ai_answer"] = new_answer
                save_inbox()
                self.reply_json(200, {"status": "ok", "ai_answer": new_answer})
            except Exception as e:
                self.reply_json(400, {"error": str(e)})
            return

        # 4. Delete item
        if self.path == "/api/delete":
            try:
                data = json.loads(body.decode("utf-8"))
                item_id = data.get("id")
                inbox_items = [x for x in inbox_items if x["id"] != item_id]
                save_inbox()
                self.reply_json(200, {"status": "ok"})
            except Exception as e:
                self.reply_json(400, {"error": str(e)})
            return

        # 5. Save settings
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

        # 6. LINE Webhook
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
                    reply_token = ev.get("replyToken", "")
                    user_msg = ev.get("message", {}).get("text", "").strip()

                    if not user_msg:
                        continue

                    token = config.get("channel_access_token", "")
                    profile = get_line_profile(user_id, token)
                    sender_name = profile.get("displayName", "ผู้ใช้งาน LINE")
                    picture_url = profile.get("pictureUrl", "")

                    # Ask AI for best suggested answer
                    ai_answer = ask_ai(user_msg, sender_name, "balanced")

                    # Check if auto_reply is enabled
                    auto_replied = False
                    if config.get("auto_reply", False) and token:
                        auto_replied = reply_line_message(reply_token, ai_answer, token)
                        if not auto_replied:
                            auto_replied = push_line_message(user_id, ai_answer, token)

                    new_item = {
                        "id": str(uuid.uuid4())[:8],
                        "user_id": user_id,
                        "reply_token": reply_token,
                        "reply_token_time": time.time(),
                        "sender_name": sender_name,
                        "picture_url": picture_url,
                        "question": user_msg,
                        "ai_answer": ai_answer,
                        "status": "sent" if auto_replied else "pending",
                        "auto_replied": auto_replied,
                        "time": time.strftime("%H:%M น.")
                    }
                    inbox_items.insert(0, new_item)
                    save_inbox()
                    sync_to_webui(user_id, sender_name, user_msg, ai_answer)
            return

        self.reply_json(404, {"error": "not_found"})


def run_server():
    load_data()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), LineWebhookHandler)
    print(f"AItoB Smart Inbox Service listening on port {PORT}...", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    run_server()
