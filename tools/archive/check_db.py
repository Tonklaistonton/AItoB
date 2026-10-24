# -*- coding: utf-8 -*-
import subprocess

wslc = "C:\\Program Files\\WSL\\wslc.exe"
script = """
import sqlite3
conn = sqlite3.connect('/app/backend/data/webui.db')
c = conn.cursor()
tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Tables:", tables)
"""

p = subprocess.Popen([wslc, "exec", "-i", "webui", "python"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
out, err = p.communicate(input=script.encode("utf-8"))
print(out.decode("utf-8", errors="ignore"))
