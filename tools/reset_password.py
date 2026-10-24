# -*- coding: utf-8 -*-
import subprocess

wslc = "C:\\Program Files\\WSL\\wslc.exe"

script = """
import sqlite3
import bcrypt

new_pwd = "12345678"
hashed = bcrypt.hashpw(new_pwd.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

conn = sqlite3.connect('/app/backend/data/webui.db')
c = conn.cursor()

# Wipe user data
wipe_tables = ['chat', 'folder', 'feedback', 'memory', 'prompt_history', 'shared_chat', 'api_key', 'oauth_session']
all_tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]

for t in wipe_tables:
    if t in all_tables:
        count = c.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        c.execute(f"DELETE FROM {t}")
        print(f"Cleared table '{t}': deleted {count} records")

email = "phanuwatgamer158@gmail.com"
c.execute("UPDATE auth SET password = ? WHERE email = ?", (hashed, email))
c.execute("UPDATE auth SET active = 1 WHERE email = ?", (email,))
print(f"Password reset for {email} to: {new_pwd}")

conn.commit()
conn.close()
print("Success!")
"""

p = subprocess.Popen([wslc, "exec", "-i", "webui", "python"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
out, err = p.communicate(input=script.encode("utf-8"))
print(out.decode("utf-8", errors="ignore"))
if err:
    print("ERR:", err.decode("utf-8", errors="ignore"))

