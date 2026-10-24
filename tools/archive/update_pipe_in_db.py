import sqlite3
from pathlib import Path

pipe_code = Path('/tmp/aitob_openwebui_pipe.py').read_text(encoding='utf-8')

conn = sqlite3.connect('/app/backend/data/webui.db')
conn.execute("UPDATE function SET content = ? WHERE id = 'aitob_assistant'", (pipe_code,))
conn.commit()
print("Updated aitob_assistant in webui.db successfully! Length:", len(pipe_code))

