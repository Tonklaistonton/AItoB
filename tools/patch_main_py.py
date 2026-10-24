# -*- coding: utf-8 -*-
import sys

target_path = '/app/backend/open_webui/main.py'
with open(target_path, 'r', encoding='utf-8') as f:
    content = f.read()

start_marker = "@app.post('/api/internal/line-message')"
end_marker = "# --- End AItoB LINE Route ---"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print("Markers not found in main.py!")
    sys.exit(1)

new_code = '''@app.post('/api/internal/line-message')
async def on_line_message(request: Request):
    data = await request.json()
    import time, uuid, json, sqlite3
    user_id = '0626e561-2dae-46fb-b5a6-58b35710c228'
    line_uid = data.get('user_id', '')
    sender = data.get('sender_name', 'ลูกค้า LINE')
    question = data.get('question', '')
    ai_answer = data.get('ai_answer', '')
    now = int(time.time())

    db_path = '/app/backend/data/webui.db'
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT id, chat FROM chat WHERE folder_id = 'folder-line' AND meta LIKE ? ORDER BY updated_at DESC LIMIT 1",
            (f'%"{line_uid}"%',)
        ).fetchone()

        msg_u_id = str(uuid.uuid4())
        msg_a_id = str(uuid.uuid4())
        hint_text = "\\n\\n---\\n*(💡 พิมพ์คำตอบใหม่แล้วกด Send เพื่อส่งเข้า LINE ทันที หรือพิมพ์ `ส่งเลย` เพื่อส่งร่างนี้ | พิมพ์ `ปิดเคส` เมื่อดูแลเสร็จเรียบร้อย)*"
        full_ai_content = f"{ai_answer}{hint_text}"

        if row:
            chat_id = row[0]
            try:
                c = json.loads(row[1])
            except Exception:
                c = {}
            curr_id = c.get('history', {}).get('currentId')
            c.setdefault('history', {}).setdefault('messages', {})
            c['history']['messages'][msg_u_id] = {
                'id': msg_u_id,
                'parentId': curr_id,
                'childrenIds': [msg_a_id],
                'role': 'user',
                'user': {'name': f"{sender} (LINE)"},
                'content': question,
                'timestamp': now,
                'models': ['aitob_assistant.assistant']
            }
            c['history']['messages'][msg_a_id] = {
                'id': msg_a_id,
                'parentId': msg_u_id,
                'childrenIds': [],
                'role': 'assistant',
                'content': full_ai_content,
                'timestamp': now + 1,
                'models': ['aitob_assistant.assistant']
            }
            if curr_id and curr_id in c['history']['messages']:
                c['history']['messages'][curr_id].setdefault('childrenIds', []).append(msg_u_id)
            c['history']['currentId'] = msg_a_id
            c.setdefault('messages', []).extend([
                {'id': msg_u_id, 'role': 'user', 'content': question, 'timestamp': now},
                {'id': msg_a_id, 'role': 'assistant', 'content': full_ai_content, 'timestamp': now + 1}
            ])
            conn.execute(
                "UPDATE chat SET updated_at = ?, chat = ? WHERE id = ?",
                (now, json.dumps(c), chat_id)
            )
        else:
            chat_id = f"line-{line_uid}-{now}"
            past_rows = conn.execute(
                "SELECT chat FROM chat WHERE meta LIKE ? ORDER BY updated_at ASC LIMIT 5",
                (f'%"{line_uid}"%',)
            ).fetchall()

            history_messages = {}
            flat_messages = []
            prev_id = None

            if past_rows:
                ctx_id = str(uuid.uuid4())
                ctx_content = f"📜 **ประวัติบทสนทนาที่ผ่านมาของคุณ {sender} จากเคสก่อนหน้า:**\\n"
                for pr in past_rows:
                    try:
                        p_chat = json.loads(pr[0])
                        for m in p_chat.get('messages', []):
                            if m.get('role') in ('user', 'assistant'):
                                r_label = sender if m.get('role') == 'user' else 'AI/Admin'
                                raw_text = m.get('content', '').split('\\n\\n---')[0][:80]
                                ctx_content += f"- **{r_label}:** {raw_text}\\n"
                    except Exception:
                        pass
                history_messages[ctx_id] = {
                    'id': ctx_id,
                    'parentId': None,
                    'childrenIds': [msg_u_id],
                    'role': 'assistant',
                    'content': ctx_content,
                    'timestamp': now - 2,
                    'models': ['aitob_assistant.assistant']
                }
                flat_messages.append({'id': ctx_id, 'role': 'assistant', 'content': ctx_content, 'timestamp': now - 2})
                prev_id = ctx_id

            history_messages[msg_u_id] = {
                'id': msg_u_id,
                'parentId': prev_id,
                'childrenIds': [msg_a_id],
                'role': 'user',
                'user': {'name': f"{sender} (LINE)"},
                'content': question,
                'timestamp': now,
                'models': ['aitob_assistant.assistant']
            }
            history_messages[msg_a_id] = {
                'id': msg_a_id,
                'parentId': msg_u_id,
                'childrenIds': [],
                'role': 'assistant',
                'content': full_ai_content,
                'timestamp': now + 1,
                'models': ['aitob_assistant.assistant']
            }
            flat_messages.extend([
                {'id': msg_u_id, 'role': 'user', 'content': question, 'timestamp': now},
                {'id': msg_a_id, 'role': 'assistant', 'content': full_ai_content, 'timestamp': now + 1}
            ])

            chat_title = f"🟢 [LINE] {sender}: {question[:25]}"
            new_chat_obj = {
                'id': chat_id,
                'title': chat_title,
                'models': ['aitob_assistant.assistant'],
                'params': {},
                'history': {
                    'currentId': msg_a_id,
                    'messages': history_messages
                },
                'messages': flat_messages
            }

            conn.execute(\'\'\'
                INSERT INTO chat (id, user_id, title, folder_id, created_at, updated_at, chat, meta, pinned, archived)
                VALUES (?, ?, ?, 'folder-line', ?, ?, ?, ?, 1, 0)
            \'\'\', (
                chat_id, user_id, chat_title,
                now, now, json.dumps(new_chat_obj),
                json.dumps({'line_user_id': line_uid, 'sender_name': sender, 'source': 'line'})
            ))

        conn.commit()
    return {"status": "ok", "chat_id": chat_id}
'''

content = content[:start_idx] + new_code + content[end_idx:]

with open(target_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Patched main.py successfully!")

