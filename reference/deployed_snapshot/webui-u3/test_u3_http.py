"""Run on the Mac host: real HTTP + one HR document/model request."""
import json
from pathlib import Path
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8002"
with urllib.request.urlopen(BASE + "/health", timeout=5) as response:
    health = json.load(response)
assert health["service"] == "aitob-assistant"
print("PASS: Assistant service health.", flush=True)


def call(arguments, key=None):
    headers = {"Content-Type": "application/json"}
    if key is not None:
        headers["Authorization"] = "Bearer " + key
    request = urllib.request.Request(
        BASE + "/chat", data=json.dumps(arguments).encode("utf-8"),
        headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


question = "บริษัทให้วันลาพักร้อนกี่วัน และต้องแจ้งล่วงหน้ากี่วัน"
for key in (None, "wrong-key"):
    status, result = call({"question": question}, key)
    assert status == 401
    assert "answer" not in result
print("PASS: Missing and invalid keys denied over HTTP.", flush=True)

hr_key = (Path.home() / "aitob-lab/gateway/credentials/hr.key").read_text().strip()
status, _ = call({"question": question, "role": "Finance"}, hr_key)
assert status == 400
print("PASS: Client role override rejected over HTTP.", flush=True)

status, result = call({"question": question, "history": []}, hr_key)
assert status == 200, (status, result.get("error"))
assert result["status"] == "complete"
assert [item["id"] for item in result["sources"]] == ["hr-leave"]
assert any(item["tool"] == "search_company_docs" for item in result["trace"])
print("Answer:", result["answer"], flush=True)
print("PASS: HR chat works through the Assistant HTTP service.", flush=True)
