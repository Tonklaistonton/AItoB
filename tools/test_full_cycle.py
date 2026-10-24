# -*- coding: utf-8 -*-
import sqlite3, json, time, uuid, urllib.request

conn = sqlite3.connect('/app/backend/data/webui.db')

# Clean old LINE test chats
conn.execute("DELETE FROM chat WHERE folder_id LIKE '%line%'")
conn.commit()

now = int(time.time()) - 3600
user_id = '0626e561-2dae-46fb-b5a6-58b35710c228'
line_uid = 'Uc17ea54a77a4bacc38249dd89d01d6ec'
sender = 'Tonton'

# 1. Insert a past closed case
m1_id = str(uuid.uuid4())
m2_id = str(uuid.uuid4())
closed_chat = {
    'id': f'line-{line_uid}-past',
    'title': f'📁 [LINE] {sender}: ขอใบเสนอราคา',
    'models': ['aitob_assistant.assistant'],
    'params': {},
    'history': {
        'currentId': m2_id,
        'messages': {
            m1_id: {'id': m1_id, 'parentId': None, 'childrenIds': [m2_id], 'role': 'user', 'content': 'ขอใบเสนอราคาแพ็กเกจ 20 คนหน่อยครับ', 'timestamp': now},
            m2_id: {'id': m2_id, 'parentId': m1_id, 'childrenIds': [], 'role': 'assistant', 'content': 'จัดส่งใบเสนอราคาให้เรียบร้อยแล้วทางอีเมลครับ', 'timestamp': now + 1}
        }
    },
    'messages': [
        {'id': m1_id, 'role': 'user', 'content': 'ขอใบเสนอราคาแพ็กเกจ 20 คนหน่อยครับ', 'timestamp': now},
        {'id': m2_id, 'role': 'assistant', 'content': 'จัดส่งใบเสนอราคาให้เรียบร้อยแล้วทางอีเมลครับ', 'timestamp': now + 1}
    ]
}

conn.execute('''
    INSERT INTO chat (id, user_id, title, folder_id, created_at, updated_at, chat, meta, pinned, archived)
    VALUES (?, ?, ?, 'folder-line-closed', ?, ?, ?, ?, 0, 0)
''', (
    f'line-{line_uid}-past', user_id, f'📁 [LINE] {sender}: ขอใบเสนอราคา',
    now, now, json.dumps(closed_chat, ensure_ascii=False),
    json.dumps({'line_user_id': line_uid, 'sender_name': sender, 'source': 'line'}, ensure_ascii=False)
))
conn.commit()
print("1. Past closed case inserted into 'folder-line-closed'.")

# 2. Simulate new incoming message from Tonton
payload = {
    'user_id': line_uid,
    'sender_name': sender,
    'question': 'สนใจเริ่มติดตั้งระบบ AI สัปดาห์หน้าเลยครับ ต้องเตรียมอะไรบ้าง',
    'ai_answer': 'สวัสดีครับคุณ Tonton ยินดีมากๆ ครับ สำหรับการติดตั้งสัปดาห์หน้า สิ่งที่ต้องเตรียมมีเพียงข้อมูลการเชื่อมต่อระบบเบื้องต้น แอดมินขออนุญาตส่ง Checklist สรุปให้ตรวจเช็คได้เลยครับ'
}
req = urllib.request.Request(
    'http://127.0.0.1:8080/api/internal/line-message',
    data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
with urllib.request.urlopen(req, timeout=5) as resp:
    res = json.load(resp)
    new_chat_id = res.get('chat_id')
    print("2. New case spawned via internal API:", new_chat_id)

# 3. Check what was created in DB for new_chat_id
row = conn.execute("SELECT id, title, folder_id, chat FROM chat WHERE id = ?", (new_chat_id,)).fetchone()
print(f"3. Chat row found: id={row[0]}, title={row[1]}, folder_id={row[2]}")
c = json.loads(row[3])
print("   Messages in new chat:")
for m in c.get('messages', []):
    print(f"   - [{m.get('role')}]: {m.get('content')[:120]}...")

