import json
import socket
import urllib.error
import urllib.request


def build_summary_payload(report, model):
    fields = [
        "input_rows", "cleaned_rows", "duplicate_rows",
        "rejected_rows", "total_amount", "currency"
    ]
    facts = {field: report[field] for field in fields}

    return {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "สรุปรายงานทำความสะอาดข้อมูลเป็นภาษาไทย 2-3 ประโยค "
                    "ใช้เฉพาะข้อเท็จจริงใน JSON ที่ให้ "
                    "ระบุจำนวนแถวต้นฉบับ แถวที่ใช้ได้ แถวซ้ำ "
                    "แถวที่ถูกปฏิเสธ และยอดรวมของแถวที่ใช้ได้ "
                    "รักษาตัวเลขและสกุลเงินตามต้นฉบับ "
                    "ห้ามเดาสาเหตุของข้อมูลผิดพลาดหรือเพิ่มข้อเท็จจริง"
                )
            },
            {
                "role": "user",
                "content": json.dumps(facts, ensure_ascii=False)
            }
        ],
        "stream": False,
        "think": False,
        "options": {"num_ctx": 4096, "num_predict": 256}
    }


def summarize_report(report, model, ollama_url):
    payload = build_summary_payload(report, model)
    request = urllib.request.Request(
        ollama_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            result = json.load(response)
        text = result["message"]["content"]
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Empty summary")
        return {"status": "ok", "text": text}
    except (TimeoutError, socket.timeout):
        return {"status": "timeout", "text": None}
    except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError):
        return {"status": "unavailable", "text": None}
