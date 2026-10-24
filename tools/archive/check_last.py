import sqlite3, json
conn = sqlite3.connect('/app/backend/data/webui.db')
row = conn.execute("SELECT id, title, folder_id, chat FROM chat WHERE folder_id = 'folder-line' ORDER BY updated_at DESC LIMIT 1").fetchone()
print("ID:", row[0])
print("Title:", row[1])
print("Folder:", row[2])
c = json.loads(row[3])
for m in c.get("messages", []):
    print(">>>", m.get("role"), ":::", repr(m.get("content")[:120]))

