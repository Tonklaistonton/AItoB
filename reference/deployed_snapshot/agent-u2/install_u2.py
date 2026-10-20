"""Install U2 into the existing Mac lab, preserving old modules and a gateway backup."""
import datetime
import os
from pathlib import Path
import shutil

package = Path(__file__).resolve().parent
lab = Path.home() / "aitob-lab"
gateway = lab / "gateway" / "gateway.py"
mcp_folder = lab / "mcp-lab"
source = gateway.read_text(encoding="utf-8")
route = '        if self.path not in ("/chat", "/rag", "/workflow/expenses", "/email/summary", "/agent/turn"):'
anchor = '        if self.path == "/agent/turn":'
if "from aitob_turn import" in source:
    raise SystemExit("U2 appears installed already; no files changed.")
if source.count(route) != 1 or source.count(anchor) != 1:
    raise SystemExit("Gateway differs from the expected A5 version; no files changed.")
for required in ("aitob_tools_server.py", "finance_server.py", "mail_tools_server.py"):
    if not (mcp_folder / required).exists():
        raise SystemExit("Missing prerequisite: " + required)

addition = '''        if self.path == "/assistant/turn":
            status, result = handle_assistant_http(
                self, identity, MODEL, OLLAMA_URL
            )
            self.reply(status, result)
            return

'''
updated = "from aitob_turn import handle_assistant_http\n" + source
updated = updated.replace(route, '        if self.path not in ("/chat", "/rag", "/workflow/expenses", "/email/summary", "/agent/turn", "/assistant/turn"):', 1)
updated = updated.replace(anchor, addition + anchor, 1)
compile(updated, str(gateway), "exec")

targets = {
    "aitob_agent_policy.py": lab / "gateway" / "aitob_agent_policy.py",
    "aitob_turn.py": lab / "gateway" / "aitob_turn.py",
    "aitob_agent.py": mcp_folder / "aitob_agent.py",
    "check_aitob_agent.py": mcp_folder / "check_aitob_agent.py",
}
for name, destination in targets.items():
    content = (package / name).read_text(encoding="utf-8")
    compile(content, str(destination), "exec")
    if destination.exists() and destination.read_text(encoding="utf-8") != content:
        raise SystemExit("Existing file differs; no files changed: " + str(destination))

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
backup = gateway.with_name("gateway_before_u2_" + stamp + ".py")
shutil.copy2(gateway, backup)
for name, destination in targets.items():
    shutil.copy2(package / name, destination)
temporary = gateway.with_name("gateway_u2_install.tmp")
temporary.write_text(updated, encoding="utf-8")
os.replace(temporary, gateway)
print("PASS: Unified agent installed; gateway syntax checked.")
print("Gateway backup:", backup.name)
print("Restart the gateway before live tests.")
