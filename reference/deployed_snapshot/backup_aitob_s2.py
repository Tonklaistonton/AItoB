"""Create a private, live SQLite and lab-source backup on the Mac host."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
from datetime import datetime


def run(args, cwd=None):
    return subprocess.run(args, cwd=cwd, check=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True).stdout


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def main():
    os.umask(0o077)
    home = Path.home()
    lab = home / "aitob-lab"
    compose = lab / "open-webui"
    if not compose.is_dir():
        raise SystemExit("STOP: Run this script on the Mac lab account.")
    agent_paths = [home / "Library/LaunchAgents" / ("com.aitob.lab." + name + ".plist")
                   for name in ("ollama", "gateway")]
    if not all(path.is_file() for path in agent_paths):
        raise SystemExit("STOP: Expected both installed AItoB LaunchAgents for this post-migration backup.")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    folder = home / "aitob-backups" / stamp
    folder.mkdir(parents=True, mode=0o700)
    folder.parent.chmod(0o700)
    database_temp = "/tmp/aitob_webui_backup_" + stamp + ".db"
    sqlite_script = '''import os, sqlite3, sys
os.umask(0o077)
source = sqlite3.connect("file:/app/backend/data/webui.db?mode=ro", uri=True, timeout=30)
destination = sqlite3.connect(sys.argv[1])
try:
    source.backup(destination)
    destination.execute("PRAGMA journal_mode=DELETE").fetchone()
finally:
    destination.close()
    source.close()
'''
    container_temp_created = False
    try:
        run(["docker", "compose", "exec", "-T", "open-webui", "python", "-c",
             sqlite_script, database_temp], cwd=compose)
        container_temp_created = True
        run(["docker", "compose", "cp", "open-webui:" + database_temp,
             str(folder / "webui.db")], cwd=compose)
        (folder / "webui.db").chmod(0o600)
    finally:
        if container_temp_created:
            run(["docker", "compose", "exec", "-T", "open-webui", "python", "-c",
                 "import pathlib,sys; pathlib.Path(sys.argv[1]).unlink()", database_temp], cwd=compose)

    connection = sqlite3.connect((folder / "webui.db").as_uri() + "?mode=ro&immutable=1", uri=True)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchall()
        if integrity != [("ok",)]:
            raise RuntimeError("Database integrity check failed")
        counts = {table: connection.execute("SELECT COUNT(*) FROM [" + table + "]").fetchone()[0]
                  for table in ("user", "chat", "function")}
    finally:
        connection.close()
    print("PASS: Consistent WebUI database backup; integrity check OK.")

    # Includes credentials: the entire backup directory is private to the lab account.
    run(["tar", "-czf", str(folder / "aitob-lab.tar.gz"),
         "--exclude=__pycache__", "--exclude=.git", "--exclude=.venv",
         "-C", str(home), "aitob-lab"])
    run(["tar", "-tzf", str(folder / "aitob-lab.tar.gz")])
    print("PASS: Lab source, configuration, credentials and sample files archived.")

    for path in agent_paths:
        (folder / path.name).write_bytes(path.read_bytes())
    print("PASS: Installed Ollama and Gateway LaunchAgents copied.")

    ids = run(["docker", "ps", "-q"]).split()
    runtime = []
    if ids:
        containers = json.loads(run(["docker", "inspect"] + ids))
        for item in containers:
            name = item["Name"].lstrip("/")
            image = item["Config"]["Image"]
            if not (image.startswith("aitob-") or name.startswith(("open-webui-", "aitob-services-"))):
                continue
            runtime.append({
                "name": name, "image_reference": image, "image_id": item["Image"],
                "entrypoint": item["Config"].get("Entrypoint"), "command": item["Config"].get("Cmd"),
                "mounts": item.get("Mounts", []),
                "ports": item["HostConfig"].get("PortBindings"),
                "restart": item["HostConfig"].get("RestartPolicy"),
            })
    (folder / "runtime.json").write_text(json.dumps(runtime, indent=2), encoding="utf-8")
    (folder / "README.txt").write_text(
        "Private AItoB backup: contains API keys and Gmail OAuth tokens.\n"
        "webui.db is a consistent SQLite backup, including accounts, chats and Functions.\n"
        "aitob-lab.tar.gz contains host lab source/configuration and credentials.\n"
        "runtime.json records running container commands, image IDs, mounts and ports.\n"
        "com.aitob.lab.*.plist files are the installed user LaunchAgents.\n"
        "Not included: Docker images, Ollama app/model files, or other WebUI volume files\n"
        "such as uploads, vector indexes and WEBUI_SECRET_KEY storage.\n"
        "This is a database/source backup, not a complete machine or volume backup.\n"
        "SQLite integrity and archive readability were checked; a restore has not been tested.\n"
        "Database record counts: " + json.dumps(counts) + "\n", encoding="utf-8")
    files = sorted(path for path in folder.iterdir() if path.is_file())
    (folder / "SHA256SUMS.txt").write_text(
        "".join(digest(path) + "  " + path.name + "\n" for path in files), encoding="ascii")
    print("PASS: Runtime settings and SHA-256 checksums recorded.")
    print("BACKUP:", folder)
    print("PRIVATE: Contains credentials. Do not upload or share this folder.")
    print("No services were restarted. Docker images/model weights are not included.")


if __name__ == "__main__":
    main()
