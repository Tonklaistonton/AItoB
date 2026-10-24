# -*- coding: utf-8 -*-
import subprocess

wslc = "C:\\Program Files\\WSL\\wslc.exe"
script = """
import sqlite3
conn = sqlite3.connect('/app/backend/data/webui.db')
c = conn.cursor()
c.execute("UPDATE user SET email = 'phanuwatgamer158@gmail.com' WHERE email = 'phanuwatgamer158@gmaii.com'")
c.execute("UPDATE auth SET email = 'phanuwatgamer158@gmail.com' WHERE email = 'phanuwatgamer158@gmaii.com'")
conn.commit()
print("Updated user:", c.execute("SELECT id, name, email FROM user").fetchall())
print("Updated auth:", c.execute("SELECT id, email FROM auth").fetchall())
conn.close()
"""

p = subprocess.Popen([wslc, "exec", "-i", "webui", "python"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
out, err = p.communicate(input=script.encode("utf-8"))
print(out.decode("utf-8", errors="ignore"))

