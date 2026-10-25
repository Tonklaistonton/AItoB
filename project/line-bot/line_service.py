"""AItoB LINE Bot Service.
- Webhook receiver with fail-closed HMAC-SHA256 signature verification.
- Generates AI draft answer via AItoB Assistant.
- Spawns/updates live chat sessions in Open WebUI (webui.db).
- Pushes admin answers and edits back to customer via LINE Messaging API.
"""
import base64
import hashlib
import hmac
import json
import os
import sqlite3
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("LINE_BOT_PORT", "8003"))
CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "").strip()
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
ASSISTANT_URL = os.environ.get("ASSISTANT_URL", "http://assistant:8002").rstrip("/")
AITOB_API_KEY = os.environ.get("AITOB_API_KEY", "").strip()
DB_PATH = os.environ.get("WEBUI_DB_PATH", "/webui-data/webui.db")


def verify_signature(secret: str, body: bytes, signature: str) -> bool:
    if not secret or not signature:
        return False
    mac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(mac).decode("utf-8")
    return hmac.compare_digest(expected, signature.strip())


def get_line_profile(user_id: str, token: str) -> str:
    if not token or not user_id:
        return "ลูกค้า LINE"
    url = f"https://api.line.me/v2/bot/profile/{user_id}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}", "User-Agent": "AItoB-LineBot/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.load(resp)
            return data.get("displayName") or "ลูกค้า LINE"
    except Exception:
        return "ลูกค้า LINE"


def ask_assistant(question: str) -> str:
    if not AITOB_API_KEY:
        # Fallback default greeting if AITOB_API_KEY is not yet configured in env
        return "สวัสดีครับ ขอบคุณที่ติดต่อ AItoB แอดมินได้รับเรื่องเรียบร้อยแล้ว จะรีบตรวจสอบและให้ข้อมูลเพิ่มเติมครับ"
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
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.load(resp)
            return data.get("answer") or "ไม่มีข้อมูลคำตอบจากผู้ช่วย"
    except Exception as err:
        print(f"Assistant draft error: {err}", flush=True)
        return "สวัสดีครับ แอดมินได้รับเรื่องเรียบร้อยแล้ว กำลังตรวจสอบข้อมูลให้ครับ"


def push_line_message(user_id: str, text: str, token: str) -> bool:
    if not token or not user_id:
        print("Missing token or user_id for LINE push", flush=True)
        return False
    url = "https://api.line.me/v2/bot/message/push"
    payload = json.dumps({
        "to": user_id,
        "messages": [{"type": "text", "text": text[:4900]}],
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "AItoB-LineBot/1.0"
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as err:
        print(f"LINE push error: {err}", flush=True)
        return False


def init_folders(conn: sqlite3.Connection, admin_id: str):
    now = int(time.time())
    conn.execute("""
        INSERT OR IGNORE INTO folder (id, parent_id, user_id, name, is_expanded, created_at, updated_at)
        VALUES ('folder-line', NULL, ?, '💬 แชทลูกค้า LINE', 1, ?, ?)
    """, (admin_id, now, now))
    conn.execute("""
        INSERT OR IGNORE INTO folder (id, parent_id, user_id, name, is_expanded, created_at, updated_at)
        VALUES ('folder-line-closed', NULL, ?, '📁 ประวัติแชท LINE (ปิดเคสแล้ว)', 0, ?, ?)
    """, (admin_id, now, now))
    conn.commit()


def sync_to_webui_db(line_uid: str, sender: str, question: str, ai_answer: str, db_path: str = DB_PATH):
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}, skipped UI sync", flush=True)
        return None

    now = int(time.time())
    try:
        with sqlite3.connect(db_path) as conn:
            admin_row = conn.execute("SELECT id FROM user WHERE role = 'admin' LIMIT 1").fetchone()
            if not admin_row:
                print("No admin user found in webui.db", flush=True)
                return None
            admin_id = admin_row[0]
            init_folders(conn, admin_id)

            row = conn.execute(
                "SELECT id, chat FROM chat WHERE folder_id = 'folder-line' AND meta LIKE ? ORDER BY updated_at DESC LIMIT 1",
                (f'%"line_user_id": "{line_uid}"%',)
            ).fetchone()

            msg_id = str(uuid.uuid4())
            formatted_content = (
                f"🟢 **ลูกค้า LINE ({sender}):**\n"
                f"> {question}\n\n"
                f"---\n"
                f"🤖 **คำตอบที่ AI ช่วยร่าง:**\n"
                f"> {ai_answer}\n\n"
                f"---\n"
                f"*(💡 พิมพ์ข้อความใหม่เพื่อตอบกลับ หรือพิมพ์ `ส่งเลย` เพื่อส่งร่างนี้เข้า LINE | พิมพ์ `ปิดเคส` เมื่อเสร็จ)*"
            )

            if row:
                chat_id = row[0]
                try:
                    c = json.loads(row[1])
                except Exception:
                    c = {}
                curr_id = c.get("history", {}).get("currentId")
                c.setdefault("history", {}).setdefault("messages", {})
                c["history"]["messages"][msg_id] = {
                    "id": msg_id,
                    "parentId": curr_id,
                    "childrenIds": [],
                    "role": "assistant",
                    "content": formatted_content,
                    "timestamp": now,
                    "models": ["aitob_assistant.assistant"]
                }
                if curr_id and curr_id in c["history"]["messages"]:
                    c["history"]["messages"][curr_id].setdefault("childrenIds", []).append(msg_id)
                c["history"]["currentId"] = msg_id
                c.setdefault("messages", []).append({
                    "id": msg_id,
                    "role": "assistant",
                    "content": formatted_content,
                    "timestamp": now
                })
                conn.execute(
                    "UPDATE chat SET updated_at = ?, chat = ? WHERE id = ?",
                    (now, json.dumps(c, ensure_ascii=False), chat_id)
                )
                conn.commit()
                return chat_id
            else:
                chat_id = f"line-{line_uid}-{now}"
                title = f"💬 [LINE] {sender}: {question[:30]}"
                new_chat = {
                    "id": chat_id,
                    "title": title,
                    "models": ["aitob_assistant.assistant"],
                    "params": {},
                    "history": {
                        "currentId": msg_id,
                        "messages": {
                            msg_id: {
                                "id": msg_id,
                                "parentId": None,
                                "childrenIds": [],
                                "role": "assistant",
                                "content": formatted_content,
                                "timestamp": now,
                                "models": ["aitob_assistant.assistant"]
                            }
                        }
                    },
                    "messages": [
                        {"id": msg_id, "role": "assistant", "content": formatted_content, "timestamp": now}
                    ]
                }
                conn.execute("""
                    INSERT INTO chat (id, user_id, title, folder_id, created_at, updated_at, chat, meta, pinned, archived)
                    VALUES (?, ?, ?, 'folder-line', ?, ?, ?, ?, 0, 0)
                """, (
                    chat_id, admin_id, title,
                    now, now, json.dumps(new_chat, ensure_ascii=False),
                    json.dumps({"line_user_id": line_uid, "sender_name": sender, "source": "line"}, ensure_ascii=False)
                ))
                conn.commit()
                return chat_id
    except Exception as err:
        print(f"Error syncing to webui.db: {err}", flush=True)
        return None



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
        # 1. Admin reply from Open WebUI
        if self.path in ("/api/reply", "/reply"):
            try:
                length = int(self.headers.get("Content-Length", "0"))
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                user_id = data.get("user_id") or data.get("id") or ""
                text = data.get("text", "")
                if not user_id or not text:
                    self.reply_json(400, {"error": "user_id_and_text_required"})
                    return
                ok = push_line_message(user_id, text, CHANNEL_ACCESS_TOKEN)
                if ok:
                    self.reply_json(200, {"status": "ok", "message": "sent"})
                else:
                    self.reply_json(500, {"error": "line_push_failed"})
            except Exception as e:
                self.reply_json(400, {"error": str(e)})
            return

        # 2. LINE Webhook
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

        sig = self.headers.get("X-Line-Signature", "")
        if not CHANNEL_SECRET or not verify_signature(CHANNEL_SECRET, body, sig):
            self.reply_json(403, {"error": "invalid_signature"})
            return

        try:
            payload = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self.reply_json(400, {"error": "invalid_json"})
            return

        self.reply_json(200, {"status": "received"})

        events = payload.get("events", [])
        if not isinstance(events, list):
            return

        for ev in events:
            if not isinstance(ev, dict):
                continue
            if ev.get("type") == "message" and ev.get("message", {}).get("type") == "text":
                user_id = ev.get("source", {}).get("userId", "")
                user_msg = (ev.get("message", {}).get("text") or "").strip()
                if not user_id or not user_msg:
                    continue

                sender_name = get_line_profile(user_id, CHANNEL_ACCESS_TOKEN)
                ai_answer = ask_assistant(user_msg)
                sync_to_webui_db(user_id, sender_name, user_msg, ai_answer)


def run_server():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), LineWebhookHandler)
    print(f"AItoB LINE Bot Gateway listening on port {PORT}...", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    run_server()