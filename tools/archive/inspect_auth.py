# -*- coding: utf-8 -*-
import subprocess

wslc = "C:\\Program Files\\WSL\\wslc.exe"
script = """
import sqlite3
conn = sqlite3.connect('/app/backend/data/webui.db')
c = conn.cursor()
for row in c.execute("SELECT id, email, password FROM auth").fetchall():
    print("Auth:", row[0], row[1], row[2][:15] + "...")
for row in c.execute("SELECT id, name, email, role FROM user").fetchall():
    print("User:", row)
"""

p = subprocess.Popen([wslc, "exec", "-i", "webui", "python"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
out, err = p.communicate(input=script.encode("utf-8"))
print(out.decode("utf-8", errors="ignore"))

