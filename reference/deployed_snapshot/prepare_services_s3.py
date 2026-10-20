"""Prepare persistent Compose services from the running lab containers; do not stop them."""
import json
import os
from pathlib import Path
import subprocess


def run(args):
    return subprocess.run(args, check=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True).stdout


def make_service(item, port, lab):
    bindings = item["HostConfig"].get("PortBindings", {})
    expected = [{"HostIp": "127.0.0.1", "HostPort": str(port)}]
    if bindings != {str(port) + "/tcp": expected}:
        raise ValueError("Unexpected port bindings; no service configuration written.")
    if item["HostConfig"].get("Privileged"):
        raise ValueError("Unexpected privileged container.")
    volumes = []
    for mount in item.get("Mounts", []):
        source = Path(mount["Source"]).resolve()
        if mount["Type"] != "bind" or lab not in source.parents:
            raise ValueError("Unexpected mount outside this lab: " + str(source))
        volumes.append({"type": "bind", "source": str(source),
                        "target": mount["Destination"], "read_only": not mount["RW"],
                        "bind": {"create_host_path": False}})
    if not volumes:
        raise ValueError("Container has no lab mounts.")
    config = item["Config"]
    service = {
        "image": item["Image"], "pull_policy": "never", "restart": "unless-stopped",
        "ports": ["127.0.0.1:" + str(port) + ":" + str(port)],
        "volumes": volumes, "environment": config.get("Env", []),
        "logging": {"driver": "json-file", "options": {"max-size": "10m", "max-file": "3"}},
    }
    for original, name in (("Entrypoint", "entrypoint"), ("Cmd", "command"),
                           ("WorkingDir", "working_dir"), ("User", "user")):
        if config.get(original):
            service[name] = config[original]
    return service


def main():
    os.umask(0o077)
    lab = (Path.home() / "aitob-lab").resolve()
    folder = lab / "services"
    path = folder / "compose.json"
    if path.exists():
        raise SystemExit("STOP: services/compose.json already exists; nothing overwritten.")
    ids = run(["docker", "ps", "-q"]).split()
    if not ids:
        raise SystemExit("STOP: No running containers found.")
    containers = json.loads(run(["docker", "inspect"] + ids))
    services = {}
    old = {}
    for name, port, image in (("gmail", 8001, "aitob-gmail-lab:day2"),
                              ("assistant", 8002, "aitob-mcp-lab:day2")):
        matches = [item for item in containers if item["Config"]["Image"] == image
                   and str(port) + "/tcp" in item["HostConfig"].get("PortBindings", {})]
        if len(matches) != 1:
            raise SystemExit("STOP: Expected one running " + name + " container.")
        services[name] = make_service(matches[0], port, lab)
        old[name] = {"id": matches[0]["Id"], "name": matches[0]["Name"].lstrip("/")}
    folder.mkdir(mode=0o700, exist_ok=True)
    folder.chmod(0o700)
    path.write_text(json.dumps({"name": "aitob-services", "services": services}, indent=2), encoding="utf-8")
    path.chmod(0o600)
    (folder / "previous-containers.json").write_text(json.dumps(old, indent=2), encoding="utf-8")
    try:
        run(["docker", "compose", "-f", str(path), "config", "--quiet"])
    except subprocess.CalledProcessError as error:
        print("STOP: Compose validation failed. Existing services are still running.")
        print(error.stderr)
        raise SystemExit(1)
    print("PASS: Gmail and Assistant Compose configuration validated.")
    print("PASS: Current image IDs, commands, ports, environment and mounts preserved.")
    print("PASS: Restart policy configured; container logs capped at 3 x 10 MB each.")
    print("CONFIG:", path)
    for name, item in old.items():
        print("CURRENT:", name, item["name"])
    print("Existing services were NOT stopped or restarted.")
    print("Configuration may contain secrets; do not share the files.")


if __name__ == "__main__":
    main()
