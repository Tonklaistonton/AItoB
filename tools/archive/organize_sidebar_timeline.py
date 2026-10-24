# -*- coding: utf-8 -*-
import sqlite3, json, time, uuid

conn = sqlite3.connect('/app/backend/data/webui.db')

now = int(time.time())
user_id = '0626e561-2dae-46fb-b5a6-58b35710c228'

# 1. Update folders
conn.execute("UPDATE folder SET name = '📁 LINE (แชทที่เชื่อมต่อ)', is_expanded = 1 WHERE id = 'folder-line'")
conn.execute("UPDATE folder SET name = '📁 ตอบอีเมล', is_expanded = 1 WHERE id = 'folder-email'")
conn.execute("UPDATE folder SET name = '📁 ตอบ LINE', is_expanded = 0 WHERE id = 'folder-line-closed'")

# 2. Archive and hide all closed cases (pinned=0, archived=1)
conn.execute("UPDATE chat SET pinned = 0, archived = 1 WHERE folder_id = 'folder-line-closed' OR id LIKE '%past%'")

# 3. Clean out corrupted test chats
conn.execute("DELETE FROM chat WHERE title LIKE '%?%'")

# 4. Set up the clean timeline chats matching the user mockup

# 4a. Active LINE Bot chat (Today - 4 minutes ago)
chat_id = 'line-bot-demo'
m_u_id = str(uuid.uuid4())
m_a_id = str(uuid.uuid4())
q_text = "สวัสดีครับ ช่วยแนะนำคอร์สเรียน AI หน่อย"
ans_text = """สวัสดีครับ! มีคอร์สเรียน AI หลายคอร์สที่น่าสนใจครับ
ขึ้นอยู่กับระดับความรู้และเป้าหมายของคุณ ผมขอแนะนำคอร์สหลักๆ ที่เหมาะกับผู้เริ่มต้นและผู้ที่ต้องการพัฒนาทักษะด้าน AI ครับ

1. คอร์สพื้นฐาน AI สำหรับผู้เริ่มต้น
2. คอร์ส Python เพื่อการทำงานกับ AI
3. คอร์สสร้างแชทบอทด้วย LLM และเครื่องมืออย่าง LangChain

ถ้าคุณสนใจด้านไหนเป็นพิเศษ แจ้งได้เลยครับ เดี๋ยวผมช่วยเลือกคอร์สที่เหมาะสมให้ครับ 😊

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
            m_u_id: {'id': m_u_id, 'parentId': None, 'childrenIds': [m_a_id], 'role': 'user', 'user': {'name': 'ลูกค้า LINE'}, 'content': q_text, 'timestamp': now - 240},
            m_a_id: {'id': m_a_id, 'parentId': m_u_id, 'childrenIds': [], 'role': 'assistant', 'content': ans_text, 'timestamp': now - 240 + 1}
        }
    },
    'messages': [
        {'id': m_u_id, 'role': 'user', 'content': q_text, 'timestamp': now - 240},
        {'id': m_a_id, 'role': 'assistant', 'content': ans_text, 'timestamp': now - 240 + 1}
    ]
}

conn.execute("DELETE FROM chat WHERE id = ?", (chat_id,))
conn.execute('''
    INSERT INTO chat (id, user_id, title, folder_id, created_at, updated_at, chat, meta, pinned, archived)
    VALUES (?, ?, 'LINE Bot', NULL, ?, ?, ?, ?, 0, 0)
''', (
    chat_id, user_id,
    now - 240, now - 240, json.dumps(chat_obj, ensure_ascii=False),
    json.dumps({'line_user_id': 'Uc17ea54a77a4bacc38249dd89d01d6ec', 'sender_name': 'ลูกค้า', 'source': 'line'}, ensure_ascii=False)
))

# 4b. Test chat (Today - 1 hour ago)
conn.execute("DELETE FROM chat WHERE id = 'chat-test-sample'")
test_obj = {
    'id': 'chat-test-sample',
    'title': 'ทดสอบ',
    'models': ['aitob_assistant.assistant'],
    'params': {},
    'history': {'currentId': None, 'messages': {}},
    'messages': []
}
conn.execute('''
    INSERT INTO chat (id, user_id, title, folder_id, created_at, updated_at, chat, meta, pinned, archived)
    VALUES ('chat-test-sample', ?, 'ทดสอบ', NULL, ?, ?, ?, '{}', 0, 0)
''', (user_id, now - 3600, now - 3600, json.dumps(test_obj)))

# 4c. Email chat (Folder ตอบอีเมล - 2 hours ago)
conn.execute("DELETE FROM chat WHERE id = 'email-chat-sample'")
email_obj = {
    'id': 'email-chat-sample',
    'title': '[โค้ด.สี่] คุณประเสริฐ: ขอให้...',
    'models': ['aitob_assistant.assistant'],
    'params': {},
    'history': {'currentId': None, 'messages': {}},
    'messages': []
}
conn.execute('''
    INSERT INTO chat (id, user_id, title, folder_id, created_at, updated_at, chat, meta, pinned, archived)
    VALUES ('email-chat-sample', ?, '[โค้ด.สี่] คุณประเสริฐ: ขอให้...', 'folder-email', ?, ?, ?, '{}', 0, 0)
''', (user_id, now - 7200, now - 7200, json.dumps(email_obj)))

# 4d. Yesterday chat (Yesterday - 24 hours ago)
conn.execute("DELETE FROM chat WHERE id = 'chat-general-yesterday'")
gen_obj = {
    'id': 'chat-general-yesterday',
    'title': 'ทั่วไป',
    'models': ['aitob_assistant.assistant'],
    'params': {},
    'history': {'currentId': None, 'messages': {}},
    'messages': []
}
conn.execute('''
    INSERT INTO chat (id, user_id, title, folder_id, created_at, updated_at, chat, meta, pinned, archived)
    VALUES ('chat-general-yesterday', ?, 'ทั่วไป', NULL, ?, ?, ?, '{}', 0, 0)
''', (user_id, now - 90000, now - 90000, json.dumps(gen_obj)))

conn.commit()
print("Organized sidebar timeline successfully!")

