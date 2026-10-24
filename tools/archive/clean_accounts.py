# -*- coding: utf-8 -*-
import subprocess

wslc = "C:\\Program Files\\WSL\\wslc.exe"

script = """
import sqlite3

conn = sqlite3.connect('/app/backend/data/webui.db')
c = conn.cursor()

tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]

user_related_tables = ['auth', 'user', 'session', 'chat', 'folder', 'feedback', 'memory']

for t in user_related_tables:
    if t in tables:
        count = c.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        c.execute(f"DELETE FROM {t}")
        print(f"Cleared table '{t}': deleted {count} records")

# Enable sign-up so the user can register fresh
c.execute("UPDATE config SET value = 'true' WHERE key = 'ui.enable_signup'")
print("Updated config: ui.enable_signup = true")

conn.commit()
conn.close()
print("All accounts cleared and Sign-Up enabled successfully!")
"""

cmd = [wslc, "exec", "-i", "webui", "python"]
p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
out, err = p.communicate(input=script.encode("utf-8"))

if p.returncode != 0:
    print("Error:", err.decode("utf-8", errors="ignore"))
else:
    print(out.decode("utf-8", errors="ignore"))

