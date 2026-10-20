"""Prepare per-user launchd jobs for the Mac lab; never stop or start services."""
import os
from pathlib import Path
import plistlib
import subprocess
import sys


def job(label, arguments, cwd, home, logs, extra_env=None):
    environment = {
        "HOME": str(home),
        "PATH": str(home / ".local/bin") + ":/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        "PYTHONUNBUFFERED": "1",
    }
    environment.update(extra_env or {})
    return {
        "Label": label,
        "ProgramArguments": arguments,
        "WorkingDirectory": str(cwd),
        "EnvironmentVariables": environment,
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 15,
        "Umask": 0o077,
        "StandardOutPath": str(logs / (label + ".out.log")),
        "StandardErrorPath": str(logs / (label + ".err.log")),
    }


def main():
    if sys.platform != "darwin":
        raise SystemExit("STOP: Run on the Mac lab account.")
    os.umask(0o077)
    home = Path.home()
    lab = home / "aitob-lab"
    agents = home / "Library/LaunchAgents"
    logs = lab / "logs"
    staging = lab / "services" / "launchagents"
    ollama = (home / ".local/bin/ollama").resolve()
    gateway = lab / "gateway/gateway.py"
    for path in (ollama, gateway, Path("/usr/bin/python3")):
        if not path.is_file():
            raise SystemExit("STOP: Missing required file: " + str(path))
    domain = "gui/" + str(os.getuid())
    check = subprocess.run(["/bin/launchctl", "print", domain],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if check.returncode != 0:
        raise SystemExit("STOP: Lab account must have an active macOS desktop session.")
    jobs = [
        job("com.aitob.lab.ollama", [str(ollama), "serve"], lab, home, logs,
            {"OLLAMA_HOST": "127.0.0.1:11434"}),
        job("com.aitob.lab.gateway", ["/usr/bin/python3", "-u", str(gateway)],
            gateway.parent, home, logs),
    ]
    for item in jobs:
        destination = agents / (item["Label"] + ".plist")
        if destination.exists():
            raise SystemExit("STOP: LaunchAgent already exists; no files overwritten: " + str(destination))
        loaded = subprocess.run(["/bin/launchctl", "print", domain + "/" + item["Label"]],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if loaded.returncode == 0:
            raise SystemExit("STOP: Job is already loaded: " + item["Label"])
    for folder in (staging, logs):
        folder.mkdir(parents=True, mode=0o700, exist_ok=True)
        folder.chmod(0o700)
    agents.mkdir(parents=True, exist_ok=True)
    # Validate both jobs before putting either in the login-start directory.
    for item in jobs:
        path = staging / (item["Label"] + ".plist")
        path.write_bytes(plistlib.dumps(item))
        path.chmod(0o600)
        subprocess.run(["/usr/bin/plutil", "-lint", str(path)], check=True)
    for item in jobs:
        filename = item["Label"] + ".plist"
        destination = agents / filename
        with destination.open("xb") as output:
            output.write((staging / filename).read_bytes())
        destination.chmod(0o600)
    print("PASS: Both LaunchAgent property lists validated and installed.")
    print("PASS: Ollama configured for localhost:11434; Gateway uses the lab working directory.")
    print("PASS: Private logs configured under:", logs)
    print("Not loaded in the current session. Existing processes are still running.")
    print("The files will be eligible to load on the lab account next macOS desktop login.")
    print("Do not log out or reboot until the supervised handover and tests are complete.")
    print("Rollback before activation: move these two com.aitob.lab.*.plist files out of ~/Library/LaunchAgents.")


if __name__ == "__main__":
    main()
