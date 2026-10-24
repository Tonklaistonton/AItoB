# -*- coding: utf-8 -*-
import subprocess
import os

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
wslc = "C:\\Program Files\\WSL\\wslc.exe"

css_file = os.path.join(repo_root, "project", "webui", "custom.css")
js_file = os.path.join(repo_root, "project", "webui", "loader.js")

with open(css_file, "rb") as f:
    css_bytes = f.read()

with open(js_file, "rb") as f:
    js_bytes = f.read()

def write_in_container(dest, data):
    dir_name = os.path.dirname(dest)
    cmd = [wslc, "exec", "-i", "webui", "sh", "-c", f"mkdir -p {dir_name} && cat > {dest}"]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate(input=data)
    if p.returncode != 0:
        print(f"Error {dest}: {stderr.decode('utf-8', errors='ignore')}")
    else:
        print(f"OK: wrote {len(data)} bytes to {dest}")

print("Deploying assets byte-for-byte (UTF-8 preserved)...")
write_in_container("/app/backend/open_webui/static/custom.css", css_bytes)
write_in_container("/app/backend/open_webui/static/loader.js", js_bytes)
write_in_container("/app/build/static/aitob/custom.css", css_bytes)
write_in_container("/app/build/static/aitob/loader.js", js_bytes)
print("Finished asset deployment.")

