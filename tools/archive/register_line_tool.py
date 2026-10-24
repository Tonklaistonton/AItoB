import sqlite3
import json
import time

conn = sqlite3.connect('/app/backend/data/webui.db')
c = conn.cursor()

admin_row = c.execute("SELECT id FROM user WHERE role = 'admin' LIMIT 1").fetchone()
admin_id = admin_row[0] if admin_row else "0626e561-2dae-46fb-b5a6-58b35710c228"

tool_id = "line_manager"
tool_name = "LINE Assistant & Inbox"

tool_code = '''"""
title: LINE Assistant & Inbox
author: AItoB
version: 0.1.0
description: เครื่องมือตรวจเช็คข้อความและตอบกลับลูกค้าใน LINE Official Account
"""

import httpx
from pydantic import BaseModel, Field

class Tools:
    class Valves(BaseModel):
        LINE_BOT_URL: str = Field(
            default="http://line-bot:8003",
            description="URL ของบริการ LINE Bot"
        )

    def __init__(self):
        self.valves = self.Valves()

    async def get_line_inbox(self) -> str:
        """
        ดึงรายการข้อความที่ลูกค้าทักเข้ามาทาง LINE พร้อมคำตอบที่ AI ช่วยร่างไว้และสถานะ
        :return: รายการข้อความของลูกค้าใน LINE
        """
        try:
            async with httpx.AsyncClient(timeout=8, trust_env=False) as client:
                res = await client.get(f"{self.valves.LINE_BOT_URL.rstrip('/')}/api/inbox")
                if res.status_code != 200:
                    return "ไม่สามารถดึงข้อความจาก LINE ได้"
                items = res.json()
                if not items:
                    return "ขณะนี้ยังไม่มีข้อความส่งเข้ามาใน LINE"
                
                result = []
                for it in items[:8]:
                    st = "รอตรวจสอบ/ส่ง" if it.get("status") != "sent" else ("AI ตอบแล้ว" if it.get("auto_replied") else "ส่งแล้ว")
                    result.append(
                        f"ID: {it.get('id')} | ลูกค้า: {it.get('sender_name')} | เวลา: {it.get('time')} | สถานะ: {st}\\n"
                        f"คำถาม: {it.get('question')}\\n"
                        f"ร่างคำตอบ AI: {it.get('ai_answer')}\\n---"
                    )
                return "\\n".join(result)
        except Exception as e:
            return f"เกิดข้อผิดพลาดในการเชื่อมต่อ: {e}"

    async def reply_to_line(self, message_id: str, reply_text: str) -> str:
        """
        ส่งคำตอบไปยังลูกค้าใน LINE โดยตรงตาม message_id
        :param message_id: รหัสของข้อความ (เช่น '63edc125')
        :param reply_text: ข้อความคำตอบที่ต้องการส่งกลับไปหาลูกค้าใน LINE
        :return: ผลการส่งข้อความ
        """
        try:
            async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
                res = await client.post(
                    f"{self.valves.LINE_BOT_URL.rstrip('/')}/api/reply",
                    json={"id": message_id, "text": reply_text}
                )
                if res.status_code == 200:
                    return f"ส่งข้อความตอบกลับเข้า LINE ของลูกค้าเรียบร้อยแล้ว: '{reply_text}'"
                err = res.json().get("message", "ส่งไม่สำเร็จ")
                return f"ส่งข้อความไม่สำเร็จ: {err}"
        except Exception as e:
            return f"เกิดข้อผิดพลาดในการส่ง: {e}"

    async def set_auto_reply(self, enable: bool) -> str:
        """
        เปิดหรือปิดโหมดให้ AI ตอบกลับลูกค้าใน LINE อัตโนมัติทันที
        :param enable: true เพื่อเปิดตอบอัตโนมัติ, false เพื่อให้คนตรวจก่อนส่ง
        :return: สถานะการตั้งค่า
        """
        try:
            async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
                res = await client.post(
                    f"{self.valves.LINE_BOT_URL.rstrip('/')}/api/settings",
                    json={"auto_reply": enable}
                )
                if res.status_code == 200:
                    status = "เปิดโหมด AI ตอบกลับอัตโนมัติทันทีแล้ว" if enable else "ปิดโหมดตอบอัตโนมัติแล้ว (ต้องกดยืนยันก่อนส่ง)"
                    return f"สำเร็จ: {status}"
                return "ไม่สามารถบันทึกการตั้งค่าได้"
        except Exception as e:
            return f"เกิดข้อผิดพลาด: {e}"
'''

specs = [
    {
        "name": "get_line_inbox",
        "description": "ดึงรายการข้อความที่ลูกค้าทักเข้ามาทาง LINE พร้อมคำตอบที่ AI ช่วยร่างไว้และสถานะ",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "reply_to_line",
        "description": "ส่งคำตอบไปยังลูกค้าใน LINE โดยตรงตาม message_id",
        "parameters": {
            "type": "object",
            "properties": {
                "message_id": {
                    "type": "string",
                    "description": "รหัสของข้อความ เช่น '63edc125'"
                },
                "reply_text": {
                    "type": "string",
                    "description": "ข้อความคำตอบที่ต้องการส่งกลับไปหาลูกค้าใน LINE"
                }
            },
            "required": ["message_id", "reply_text"]
        }
    },
    {
        "name": "set_auto_reply",
        "description": "เปิดหรือปิดโหมดให้ AI ตอบกลับลูกค้าใน LINE อัตโนมัติทันที",
        "parameters": {
            "type": "object",
            "properties": {
                "enable": {
                    "type": "boolean",
                    "description": "true เพื่อเปิดตอบอัตโนมัติ, false เพื่อให้คนตรวจก่อนส่ง"
                }
            },
            "required": ["enable"]
        }
    }
]

meta = {
    "description": "เครื่องมือตรวจเช็คข้อความและตอบกลับลูกค้าใน LINE Official Account",
    "manifest": {}
}

valves = {
    "LINE_BOT_URL": "http://line-bot:8003"
}

now = int(time.time())

# Insert or replace tool
c.execute("DELETE FROM tool WHERE id = ?", (tool_id,))
c.execute("""
    INSERT INTO tool (id, user_id, name, content, specs, meta, valves, updated_at, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    tool_id,
    admin_id,
    tool_name,
    tool_code,
    json.dumps(specs, ensure_ascii=False),
    json.dumps(meta, ensure_ascii=False),
    json.dumps(valves, ensure_ascii=False),
    now,
    now
))

# Also add ui banner so the user can easily open Smart Inbox from Open WebUI
banner_item = [{
    "id": "line-smart-inbox",
    "type": "info",
    "title": "🟢 LINE Official Connected",
    "content": "เชื่อมต่อ LINE Bot สำเร็จแล้ว | [คลิกเปิดหน้าต่างตอบแชทสด Smart Inbox](http://localhost:8003) หรือพิมพ์ 'เช็คไลน์' ในแชทได้ทันที",
    "dismissible": True,
    "timestamp": now
}]

c.execute("DELETE FROM config WHERE key = 'ui.banners'")
c.execute("INSERT INTO config (key, value, updated_at) VALUES ('ui.banners', ?, ?)", (
    json.dumps(banner_item, ensure_ascii=False),
    now
))

# Update dual_copilot and line_copilot params to allow tool access
for m_id in ('dual_copilot', 'line_copilot'):
    row = c.execute("SELECT meta, params FROM model WHERE id = ?", (m_id,)).fetchone()
    if row:
        m_meta = json.loads(row[0] or "{}")
        m_params = json.loads(row[1] or "{}")
        m_meta["tool_ids"] = [tool_id]
        m_params["tools"] = [tool_id]
        c.execute("UPDATE model SET meta = ?, params = ?, updated_at = ? WHERE id = ?", (
            json.dumps(m_meta, ensure_ascii=False),
            json.dumps(m_params, ensure_ascii=False),
            now,
            m_id
        ))

conn.commit()
print("Tool registered, banner created, and models updated successfully!")
