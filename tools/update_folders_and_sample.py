# -*- coding: utf-8 -*-
import sqlite3, json, time, uuid

conn = sqlite3.connect('/app/backend/data/webui.db')

# 1. Update folders to match screenshot
conn.execute("UPDATE folder SET name = '📁 LINE (แชทที่เชื่อมต่อ)' WHERE id = 'folder-line'")
conn.execute("UPDATE folder SET name = '📁 ตอบอีเมล' WHERE id = 'folder-email'")
conn.execute("UPDATE folder SET name = '📁 ตอบ LINE' WHERE id = 'folder-line-closed'")

# 2. Insert or update the demo LINE Bot chat
now = int(time.time())
user_id = '0626e561-2dae-46fb-b5a6-58b35710c228'
chat_id = 'line-bot-demo'

m_u_id = str(uuid.uuid4())
m_a_id = str(uuid.uuid4())

q_text = "สวัสดีครับ ช่วยแนะนำคอร์สเรียน AI หน่อย"
ans_text = """สวัสดีครับ! 😊
ตอนนี้มีคอร์สเรียน AI หลายคอร์สที่น่าสนใจ ผมขอแนะนำคอร์สหลักๆ ที่เหมาะกับผู้เริ่มต้นและผู้ที่ต้องการพัฒนาทักษะด้าน AI ครับ

1. คอร์สพื้นฐาน AI สำหรับผู้เริ่มต้น (เข้าใจง่าย ใช้ได้จริง)
2. คอร์ส Python เพื่อการทำงานกับ AI (เน้นลงมือทำ)
3. คอร์สสร้างแชทบอทด้วย LLM และเครื่องมืออย่าง LangChain (เหมาะกับสายพัฒนา)

ถ้าคุณสนใจด้านไหนเป็นพิเศษ แจ้งได้เลยนะครับ เดี๋ยวผมช่วยเลือกคอร์สที่เหมาะสมให้ครับ 🙌

---
*(💡 พิมพ์คำตอบใหม่แล้วกด Send เพื่อส่งเข้า LINE ทันที หรือพิมพ์ `ส่งเลย` เพื่อส่งร่างนี้ | พิมพ์ `ปิดเคส` เมื่อดูแลเสร็จเรียบร้อย)*"""

chat_obj = {
    'id': chat_id,
    'title': 'LINE Bot',
    'models': ['aitob_assistant.assistant'],
    'params': {},
    'history': {
        'currentId': m_a_id,
        'messages': {
            m_u_id: {
                'id': m_u_id,
                'parentId': None,
                'childrenIds': [m_a_id],
                'role': 'user',
                'user': {'name': 'ลูกค้า LINE'},
                'content': q_text,
                'timestamp': now - 60
            },
            m_a_id: {
                'id': m_a_id,
                'parentId': m_u_id,
                'childrenIds': [],
                'role': 'assistant',
                'content': ans_text,
                'timestamp': now
            }
        }
    },
    'messages': [
        {'id': m_u_id, 'role': 'user', 'content': q_text, 'timestamp': now - 60},
        {'id': m_a_id, 'role': 'assistant', 'content': ans_text, 'timestamp': now}
    ]
}

conn.execute("DELETE FROM chat WHERE id = ?", (chat_id,))
conn.execute('''
    INSERT INTO chat (id, user_id, title, folder_id, created_at, updated_at, chat, meta, pinned, archived)
    VALUES (?, ?, ?, 'folder-line', ?, ?, ?, ?, 1, 0)
''', (
    chat_id, user_id, 'LINE Bot',
    now, now, json.dumps(chat_obj, ensure_ascii=False),
    json.dumps({'line_user_id': 'Uc17ea54a77a4bacc38249dd89d01d6ec', 'sender_name': 'ลูกค้า', 'source': 'line'}, ensure_ascii=False)
))

conn.commit()
print("Folders and sample chat updated successfully!")

