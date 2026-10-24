import sqlite3

tool_code = '''"""
title: LINE Assistant & Inbox Manager
author: AItoB
version: 0.2.0
description: เครื่องมือตรวจเช็คข้อความ ตอบกลับลูกค้าใน LINE Official Account และจัดการเคส
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
                        f"ID: {it.get('id')} | LINE User: {it.get('user_id')} | ลูกค้า: {it.get('sender_name')} | เวลา: {it.get('time')} | สถานะ: {st}\\n"
                        f"คำถาม: {it.get('question')}\\n"
                        f"ร่างคำตอบ AI: {it.get('ai_answer')}\\n---"
                    )
                return "\\n".join(result)
        except Exception as e:
            return f"เกิดข้อผิดพลาดในการเชื่อมต่อ: {e}"

    async def reply_to_customer(self, customer_user_id_or_message_id: str, message_to_send: str) -> str:
        """
        ส่งข้อความตอบกลับไปยัง LINE ของลูกค้าโดยตรง โดยระบุ User ID ของลูกค้า หรือ Message ID
        :param customer_user_id_or_message_id: User ID ของลูกค้า (เช่น 'Uc17ea54a77a4bacc38249dd89d01d6ec') หรือ ID ของข้อความ
        :param message_to_send: ข้อความคำตอบที่ต้องการส่งกลับไปหาลูกค้าใน LINE
        :return: ผลการส่งข้อความ
        """
        try:
            async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
                res = await client.post(
                    f"{self.valves.LINE_BOT_URL.rstrip('/')}/api/reply",
                    json={"user_id": customer_user_id_or_message_id, "id": customer_user_id_or_message_id, "text": message_to_send}
                )
                if res.status_code == 200:
                    return f"✓ ส่งข้อความเข้า LINE ของลูกค้าเรียบร้อยแล้ว: '{message_to_send}'"
                err = res.json().get("message", "ส่งไม่สำเร็จ")
                return f"ไม่สามารถส่งข้อความได้: {err}"
        except Exception as e:
            return f"เกิดข้อผิดพลาดในการเชื่อมต่อ: {e}"

    async def close_line_case(self, chat_id: str) -> str:
        """
        ปิดเคสการสนทนานี้ และย้ายห้องแชทเข้าสู่โฟลเดอร์ '📁 LINE (เคสที่ปิดแล้ว)'
        :param chat_id: รหัสห้องแชทในระบบ
        :return: ผลการปิดเคส
        """
        import sqlite3, time
        try:
            with sqlite3.connect('/app/backend/data/webui.db') as conn:
                conn.execute(
                    "UPDATE chat SET folder_id = 'folder-line-closed', updated_at = ? WHERE id = ?",
                    (int(time.time()), chat_id)
                )
                conn.commit()
            return "📁 ปิดเคสนี้เรียบร้อยแล้ว ย้ายห้องแชทเข้าสู่โฟลเดอร์ '📁 LINE (เคสที่ปิดแล้ว)' เรียบร้อยครับ"
        except Exception as e:
            return f"ไม่สามารถปิดเคสได้: {e}"
'''

conn = sqlite3.connect('/app/backend/data/webui.db')
conn.execute("UPDATE tool SET content = ? WHERE id = 'line_manager'", (tool_code,))
conn.commit()
print("line_manager tool updated successfully")

