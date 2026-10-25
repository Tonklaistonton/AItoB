"""
title: AItoB Assistant
author: AItoB Lab
version: 0.1.3
required_open_webui_version: 0.12.3
description: Per-user authenticated local agent for Gmail, expenses CSV and company documents.
"""

import html
import re
import httpx
from pydantic import BaseModel, Field


def safe_text(value):
    value = html.escape(str(value), quote=False).replace("\n", " ")[:350]
    return re.sub(r"([\\`*\[\]()_])", r"\\\1", value)


def render_answer(result):
    if not isinstance(result, dict) or not isinstance(result.get("answer"), str):
        raise ValueError("Invalid assistant response")
    text = result["answer"]
    if result.get("status") != "complete":
        text += "\n\n> คำตอบยังไม่สมบูรณ์ กรุณาลองระบุคำขอให้สั้นลง"
    lines = []
    seen = set()
    for source in result.get("sources", []):
        if not isinstance(source, dict):
            continue
        source_id = source.get("id")
        if (
            not isinstance(source_id, str)
            or re.fullmatch(r"[A-Za-z0-9_-]{1,128}", source_id) is None
            or source_id in seen
        ):
            continue
        seen.add(source_id)
        title = source.get("title") or source.get("subject") or source_id
        note = " — ใช้ข้อความบางส่วน" if source.get("truncated") else ""
        lines.append("- " + safe_text(title) + " `[" + source_id + "]`" + note)
    if lines:
        text += "\n\n**แหล่งข้อมูลที่ระบบใช้**\n\n" + "\n".join(lines)
    return text


async def save_export_for_user(report, user_id):
    # Deferred imports keep non-export chat behavior independent of this feature.
    import asyncio
    import hashlib
    import io
    import uuid
    from open_webui.models.files import Files, FileForm
    from open_webui.storage.provider import Storage

    content = report.get("content")
    if not isinstance(content, str) or not user_id:
        raise ValueError("invalid_export")
    raw = content.encode("utf-8")
    if len(raw) > 2000000 or hashlib.sha256(raw).hexdigest() != report.get("sha256"):
        raise ValueError("export_integrity_failed")
    file_id = str(uuid.uuid4())
    name = report.get("filename", "expenses_cleaned.csv")
    if name not in (
        "expenses_cleaned.csv",
        "expenses_uploaded_cleaned.csv",
        "expenses_uploaded_audit.csv",
    ):
        raise ValueError("invalid_export_filename")
    _, storage_path = await asyncio.to_thread(
        Storage.upload_file,
        io.BytesIO(raw),
        file_id + "_" + name,
        {"OpenWebUI-User-Id": user_id, "OpenWebUI-File-Id": file_id},
    )
    try:
        record = await Files.insert_new_file(
            user_id,
            FileForm(
                id=file_id,
                filename=name,
                path=storage_path,
                hash=report["sha256"],
                data={"status": "completed"},
                meta={"name": name, "size": len(raw), "content_type": "text/csv"},
            ),
        )
        if record is None:
            raise ValueError("file_registration_failed")
    except Exception:
        # Only delete the object created by this call, never a user's input file.
        await asyncio.to_thread(Storage.delete_file, storage_path)
        raise
    label = (
        "ดาวน์โหลดเหตุผลรายแถว"
        if name == "expenses_uploaded_audit.csv"
        else "ดาวน์โหลด CSV ที่ทำความสะอาดแล้ว"
    )
    return "[" + label + "](/api/v1/files/" + file_id + "/content/" + name + ")"


async def fetch_export(base_url, key, user_id):
    async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
        response = await client.post(
            base_url.rstrip("/") + "/finance/export",
            headers={"Authorization": "Bearer " + key.strip()},
            json={},
        )
    if response.status_code == 403:
        return "บัญชีนี้ไม่มีสิทธิ์ดาวน์โหลด CSV ค่าใช้จ่าย"
    if response.status_code == 401:
        return "AItoB API key ไม่ถูกต้อง กรุณาตรวจ User Valves"
    if response.status_code == 404:
        return "ยังไม่พบไฟล์ผลลัพธ์ กรุณาทำความสะอาด CSV ก่อน"
    if response.status_code != 200:
        return "ยังส่งออกไฟล์ไม่ได้ กรุณาตรวจบริการ Finance export"
    return await save_export_for_user(response.json(), user_id)


def original_user_question(value, metadata):
    # WebUI v0.12.3 prepends server-generated attachment tags to user messages.
    # Its injected metadata preserves the prompt before RAG context is applied.
    base = metadata.get("base_user_prompt") if isinstance(metadata, dict) else None
    text = base if isinstance(base, str) else value
    if not isinstance(text, str):
        return text
    return re.sub(
        r"\A\s*<attached_files>.*?</attached_files>\s*", "", text, count=1, flags=re.S
    )


async def process_attached_file(base_url, key, user_id, files):
    import asyncio
    import base64
    import hashlib
    from pathlib import Path

    # Domain permission before reading the attachment or its storage path.
    async with httpx.AsyncClient(timeout=40, trust_env=False) as client:
        headers = {"Authorization": "Bearer " + key.strip()}
        gate = await client.post(
            base_url.rstrip("/") + "/finance/authorize", headers=headers, json={}
        )
        if gate.status_code == 403:
            return "บัญชีนี้ไม่มีสิทธิ์ประมวลผลไฟล์ค่าใช้จ่าย"
        if gate.status_code != 200:
            return "ตรวจสิทธิ์ Finance ไม่สำเร็จ กรุณาตรวจ key และบริการ"
        if (
            not isinstance(files, list)
            or len(files) != 1
            or not isinstance(files[0], dict)
        ):
            return "กรุณาเริ่มแชตใหม่และแนบไฟล์ CSV หรือ Excel เพียงหนึ่งไฟล์"
        item = files[0]
        file_id = item.get("id") or (item.get("file") or {}).get("id")
        if (
            not isinstance(file_id, str)
            or re.fullmatch(r"[A-Za-z0-9_-]{1,128}", file_id) is None
        ):
            return "ไม่พบรหัสไฟล์แนบที่รองรับ"
        from open_webui.models.files import Files
        from open_webui.storage.provider import Storage

        record = await Files.get_file_by_id_and_user_id(file_id, user_id)
        if record is None or record.user_id != user_id:
            return "ไม่พบไฟล์แนบที่คุณเป็นเจ้าของ"
        name = record.filename
        if not isinstance(name, str) or not name.lower().endswith((".csv", ".xlsx")):
            return "รองรับเฉพาะ CSV และ Excel .xlsx"
        size = (record.meta or {}).get("size")
        if isinstance(size, (int, float)) and size > 1000000:
            return "ไฟล์ต้องมีขนาดไม่เกิน 1 MB"

        def load_owned_file():
            resolved = Storage.get_file(record.path)
            with Path(resolved).open("rb") as stream:
                return stream.read(1000001)

        raw = await asyncio.to_thread(load_owned_file)
        if len(raw) > 1000000:
            return "ไฟล์ต้องมีขนาดไม่เกิน 1 MB"
        response = await client.post(
            base_url.rstrip("/") + "/finance/upload",
            headers=headers,
            json={
                "filename": name,
                "content_base64": base64.b64encode(raw).decode("ascii"),
            },
        )
    if response.status_code != 200:
        error = response.json().get("error", "invalid_upload_file")
        messages = {
            "expected_expense_id_vendor_amount": "หัวตารางต้องเป็น expense_id, vendor, amount ตามลำดับ",
            "one_sheet_required": "ไฟล์ Excel ต้องมีเพียงหนึ่งชีต",
            "formulas_not_allowed": "กรุณาใช้ค่าข้อมูลแทนสูตรใน Excel",
            "row_limit": "รองรับไม่เกิน 1,000 แถว",
            "csv_or_xlsx_required": "รองรับเฉพาะ CSV และ Excel .xlsx",
        }
        return "ยังประมวลผลไฟล์ไม่ได้: " + messages.get(
            error, "ตรวจรูปแบบไฟล์และใช้ตัวอย่างที่กำหนด"
        )
    result = response.json()
    if result.get("input_sha256") != hashlib.sha256(raw).hexdigest():
        raise ValueError("input_integrity_failed")
    summary = result["summary"]
    numbers = [
        summary[k]
        for k in ("input_rows", "cleaned_rows", "duplicate_rows", "rejected_rows")
    ]
    if (
        any(type(n) is not int or not 0 <= n <= 1000 for n in numbers)
        or sum(numbers[1:]) != numbers[0]
    ):
        raise ValueError("invalid_summary_counts")
    clean_link = await save_export_for_user(result["cleaned"], user_id)
    audit_link = await save_export_for_user(result["audit"], user_id)
    lines = [
        "ประมวลผลไฟล์แนบแล้วด้วยกฎตรวจข้อมูลและยอด Decimal",
        "",
        "**ยอดที่ผ่านตรวจ: " + summary["total_amount"] + " บาท**",
        "",
        "| ผลตรวจ | จำนวนแถว | สัดส่วนเทียบก่อนตรวจ |",
        "|---|---:|---|",
    ]
    for label, n in zip(("ก่อนตรวจ", "ผ่าน", "ซ้ำ", "ปฏิเสธ"), numbers):
        length = round(20 * n / max(1, numbers[0]))
        lines.append("| " + label + " | " + str(n) + " | " + "█" * length + " |")
    lines += [
        "",
        clean_link,
        "",
        audit_link,
        "",
        "กราฟเทียบจำนวนแถว ไม่ใช่ผลประหยัดเวลา • ไฟล์แนบนี้ไม่เขียนทับ CSV เดโมเดิม",
        "รหัสตรวจไฟล์: `" + result["input_sha256"] + "`",
    ]
    return "\n".join(lines)


class Pipe:
    class Valves(BaseModel):
        BASE_URL: str = Field(
            default="http://assistant:8002",
            description="AItoB Assistant service URL",
        )
        LINE_CHANNEL_SECRET: str = Field(
            default="",
            description="LINE Channel Secret (from LINE Developers Console)",
            json_schema_extra={"input": {"type": "password"}},
        )
        LINE_CHANNEL_ACCESS_TOKEN: str = Field(
            default="",
            description="LINE Channel Access Token (Long-lived)",
        )
        LINE_BOT_URL: str = Field(
            default="http://line-bot:8003",
            description="AItoB LINE Bot Service URL",
        )

    class UserValves(BaseModel):
        AITOB_API_KEY: str = Field(
            default="",
            description="Your own AItoB API key; never enter it in a chat message",
            json_schema_extra={"input": {"type": "password"}},
        )

    def __init__(self):
        self.valves = self.Valves()

    async def sync_line_settings(self):
        secret = (self.valves.LINE_CHANNEL_SECRET or "").strip()
        token = (self.valves.LINE_CHANNEL_ACCESS_TOKEN or "").strip()
        if not secret and not token:
            return
        try:
            async with httpx.AsyncClient(timeout=4, trust_env=False) as client:
                await client.post(
                    f"{self.valves.LINE_BOT_URL.rstrip('/')}/api/settings",
                    json={
                        "channel_secret": secret,
                        "channel_access_token": token,
                    }
                )
        except Exception:
            pass

    async def handle_line_inbox(self):
        try:
            async with httpx.AsyncClient(timeout=6, trust_env=False) as client:
                res = await client.get(f"{self.valves.LINE_BOT_URL.rstrip('/')}/api/inbox")
                if res.status_code != 200:
                    return "ไม่สามารถเชื่อมต่อ LINE Bot Service ได้ กรุณาตรวจบริการพอร์ต 8003"
                items = res.json()
        except Exception as e:
            return f"เชื่อมต่อ LINE Bot ไม่สำเร็จ: {e}"

        if not items:
            return (
                "### 📬 กล่องข้อความ LINE (ยังไม่มีข้อความส่งเข้ามา)\n\n"
                "เมื่อมีลูกค้าทักเข้ามาทาง LINE ข้อความจะแสดงที่นี่แบบ Real-time\n\n"
                "👉 [คลิกเพื่อเปิดหน้าต่างตอบแชทสด Smart Inbox](/inbox)"
            )

        pending = [x for x in items if x.get("status") != "sent"]
        lines = [
            f"### 📬 กล่องข้อความ LINE (รอตอบ {len(pending)} รายการ / ทั้งหมด {len(items)} รายการ)",
            "",
            "> 💡 **วิธีตอบกลับ:** พิมพ์คำสั่ง `ตอบไลน์ [รหัส] [ข้อความของคุณ]` หรือ [คลิกเปิด Smart Inbox แชทสดพร้อมเสียงเตือน](/inbox)",
            ""
        ]

        for it in items[:8]:
            icon = "🟡 [รอตอบ]" if it.get("status") != "sent" else ("🤖 [AI ตอบแล้ว]" if it.get("auto_replied") else "🟢 [ส่งแล้ว]")
            lines.append(f"#### {icon} **รหัส `{it.get('id')}` — {it.get('sender_name', 'ลูกค้า')}** ({it.get('time', '')})")
            lines.append(f"- **คำถาม:** {it.get('question', '')}")
            lines.append(f"- **คำตอบที่ AI ช่วยร่าง:**")
            ans = it.get('ai_answer', '').replace('\n', '\n  > ')
            lines.append(f"  > {ans}")
            if it.get("status") != "sent":
                lines.append(f"- *พิมพ์คำสั่งเพื่อส่งตอบ:* `ตอบไลน์ {it.get('id')} {it.get('ai_answer', '')[:50]}...`")
            lines.append("")

        return "\n".join(lines)

    async def handle_line_reply(self, text: str):
        parts = text.strip().split(maxsplit=2)
        if len(parts) < 3:
            return "กรุณาระบุรูปแบบ: `ตอบไลน์ [รหัสข้อความ] [ข้อความที่ต้องการส่ง]`\nตัวอย่าง: `ตอบไลน์ 63edc125 สวัสดีครับ ยินดีให้บริการครับ`"
        item_id = parts[1].strip()
        reply_text = parts[2].strip()

        try:
            headers = {"Authorization": f"Bearer {self.valves.LINE_CHANNEL_SECRET}"} if self.valves.LINE_CHANNEL_SECRET else {}
            async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
                res = await client.post(
                    f"{self.valves.LINE_BOT_URL.rstrip('/')}/api/reply",
                    headers=headers,
                    json={"id": item_id, "text": reply_text}
                )
                if res.status_code == 200:
                    return f"✅ **ส่งคำตอบเข้า LINE เรียบร้อยแล้ว!**\n\n> ข้อความ: {reply_text}\n\n[ดูสถานะล่าสุดใน Smart Inbox](/inbox)"
                err = res.json().get("message", "ส่งไม่สำเร็จ")
                return f"❌ ไม่สามารถส่งได้: {err}"
        except Exception as e:
            return f"เชื่อมต่อ LINE Bot ไม่สำเร็จ: {e}"

    async def handle_line_toggle(self, enable: bool):
        try:
            async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
                res = await client.post(
                    f"{self.valves.LINE_BOT_URL.rstrip('/')}/api/settings",
                    json={"auto_reply": enable}
                )
                if res.status_code == 200:
                    status_text = "เปิดโหมด: AI ตอบกลับข้อความใน LINE ทันทีอัตโนมัติ" if enable else "ปิดโหมดตอบอัตโนมัติ (ให้แอดมินตรวจและกดส่งเอง)"
                    return f"⚙️ **ตั้งค่าสำเร็จ:** {status_text}\n\n[ดูการตั้งค่าใน Smart Inbox](/inbox)"
                return "ไม่สามารถเปลี่ยนการตั้งค่าได้"
        except Exception as e:
            return f"เชื่อมต่อ LINE Bot ไม่สำเร็จ: {e}"

    async def handle_close_case(self, chat_id: str):
        import sqlite3, time
        try:
            with sqlite3.connect('/app/backend/data/webui.db') as conn:
                conn.execute(
                    "UPDATE chat SET folder_id = 'folder-line-closed', pinned = 0, archived = 1, updated_at = ? WHERE id = ?",
                    (int(time.time()), chat_id)
                )
                conn.commit()
            return "📁 **ปิดเคสนี้เรียบร้อยแล้ว**\n\n- ย้ายและซ่อนห้องแชทออกจากรายการหลักเรียบร้อยครับ (จัดเก็บในประวัติ)\n- หากลูกค้าท่านนี้ทัก LINE เข้ามาใหม่ ระบบจะเปิดเป็นเคสใหม่พร้อมดึงประวัติเดิมมาต่อให้อัตโนมัติครับ"
        except Exception as e:
            return f"ไม่สามารถปิดเคสได้: {e}"

    async def handle_direct_line_reply(self, chat_id: str, text: str):
        import sqlite3, json
        line_uid = ""
        try:
            with sqlite3.connect('/app/backend/data/webui.db') as conn:
                row = conn.execute("SELECT meta FROM chat WHERE id = ?", (chat_id,)).fetchone()
                if row and row[0]:
                    meta = json.loads(row[0])
                    line_uid = meta.get("line_user_id", "")
        except Exception:
            pass
        if not line_uid:
            parts = chat_id.replace("line-", "").split("-")
            line_uid = parts[0]

        try:
            headers = {"Authorization": f"Bearer {self.valves.LINE_CHANNEL_SECRET}"} if self.valves.LINE_CHANNEL_SECRET else {}
            async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
                res = await client.post(
                    f"{self.valves.LINE_BOT_URL.rstrip('/')}/api/reply",
                    headers=headers,
                    json={"user_id": line_uid, "text": text}
                )
                if res.status_code == 200:
                    return f"✅ **ส่งเข้า LINE ของลูกค้าเรียบร้อยแล้ว!**\n\n> *\"{text}\"*\n\n*(ส่งถึงลูกค้าแล้ว • หากคุยจบเรื่องแล้ว สามารถพิมพ์ `ปิดเคส` เพื่อย้ายเก็บได้เลยครับ)*"
                err = res.json().get("message", "ส่งไม่สำเร็จ")
                return f"❌ ไม่สามารถส่งข้อความได้: {err}"
        except Exception as e:
            return f"เชื่อมต่อ LINE Bot ไม่สำเร็จ: {e}"

    async def handle_send_draft(self, chat_id: str, messages: list):
        draft = ""
        for m in reversed(messages):
            if isinstance(m, dict) and m.get("role") == "assistant":
                draft = m.get("content", "").strip()
                break
        if not draft and chat_id:
            import sqlite3, json
            try:
                with sqlite3.connect('/app/backend/data/webui.db') as conn:
                    row = conn.execute("SELECT chat FROM chat WHERE id = ?", (chat_id,)).fetchone()
                    if row and row[0]:
                        c = json.loads(row[0])
                        for m in reversed(c.get('messages', [])):
                            if m.get('role') == 'assistant':
                                draft = m.get('content', '').strip()
                                break
            except Exception:
                pass
        if not draft:
            return "ไม่พบคำตอบร่างของ AI กรุณาพิมพ์ข้อความที่ต้องการส่งได้เลยครับ"
        if "🤖 **คำตอบที่ AI ช่วยร่าง:**" in draft:
            part = draft.split("🤖 **คำตอบที่ AI ช่วยร่าง:**", 1)[1]
            part = part.split("\n\n---", 1)[0].split("\n\n*(", 1)[0]
            lines = [l.lstrip("> ").strip() for l in part.strip().split("\n")]
            clean_draft = "\n".join(lines).strip()
        else:
            clean_draft = draft.split("\n\n---")[0].split("\n\n*")[0].strip()
        return await self.handle_direct_line_reply(chat_id, clean_draft)

    async def handle_ask_ai_draft(self, question: str, chat_id: str):
        try:
            async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
                res = await client.post(
                    f"{self.valves.LINE_BOT_URL.rstrip('/')}/api/ask-ai",
                    json={"question": question}
                )
                if res.status_code == 200:
                    ans = res.json().get("answer", "")
                    return f"🤖 **คำตอบที่ AI ช่วยร่าง:**\n\n{ans}\n\n---\n*(พิมพ์ `ส่งเลย` เพื่อส่งร่างนี้เข้า LINE หรือพิมพ์คำตอบที่ต้องการได้ทันที)*"
        except Exception:
            pass
        return "🤖 ขออภัยครับ ไม่สามารถร่างคำตอบจาก AI ได้ในขณะนี้ กรุณาพิมพ์ข้อความที่ต้องการตอบได้โดยตรงครับ"

    def pipes(self):
        return [{"id": "assistant", "name": "AItoB Assistant"}]

    async def pipe(
        self,
        body: dict,
        __user__: dict = None,
        __event_emitter__=None,
        __task__: str = None,
        __files__: list = None,
        __metadata__: dict = None,
    ):
        await self.sync_line_settings()
        # Never execute business operations for title/tag/background generation.
        if __task__ is not None:
            return ""
        if not isinstance(__user__, dict) or not __user__.get("id"):
            return "กรุณาลงชื่อเข้าใช้ก่อนใช้งาน AItoB"
        # Check question first
        messages = body.get("messages", [])
        if not isinstance(messages, list):
            return "รูปแบบข้อความไม่ถูกต้อง"
        user_indices = [
            index
            for index, item in enumerate(messages)
            if isinstance(item, dict) and item.get("role") == "user"
        ]
        if not user_indices:
            return "กรุณาพิมพ์คำถาม"
        index = user_indices[-1]
        question = original_user_question(messages[index].get("content"), __metadata__)
        if not isinstance(question, str) or not 1 <= len(question.strip()) <= 1000:
            return "กรุณาส่งคำถามแบบข้อความ ความยาวไม่เกิน 1,000 ตัวอักษร"

        # Direct LINE Bot operations without requiring AITOB_API_KEY
        q_clean = question.strip()
        q_lower = q_clean.lower()

        # Seamless LINE Case Chat handling
        chat_id = (__metadata__ or {}).get("chat_id", "") or body.get("chat_id", "")
        if chat_id.startswith("line-") or "line" in chat_id.lower():
            if q_lower in ("ปิดเคส", "/close", "ปิดงาน", "จบเคส", "close", "close case"):
                return await self.handle_close_case(chat_id)
            if q_lower in ("ส่งเลย", "ส่งอันนี้เลย", "ตกลงส่ง", "ยืนยัน", "ส่งข้อความนี้", "yes", "send"):
                return await self.handle_send_draft(chat_id, messages)
            if q_lower.startswith("ai:") or q_lower.startswith("ถาม ai:") or q_lower.startswith("ปรึกษา:") or q_lower.startswith("ร่างใหม่:"):
                raw_q = re.sub(r"^(ai:|ถาม ai:|ปรึกษา:|ร่างใหม่:)\s*", "", q_clean, flags=re.I)
                return await self.handle_ask_ai_draft(raw_q, chat_id)
            return await self.handle_direct_line_reply(chat_id, q_clean)

        if q_lower in ("เช็คไลน์", "เช็คแชทไลน์", "ดูแชทไลน์", "ดูข้อความไลน์", "มีคนทักไลน์ไหม", "มีคนทักไลน์มาไหม", "กล่องข้อความไลน์", "inbox line", "line inbox", "/line", "/line-inbox"):
            return await self.handle_line_inbox()

        if q_lower.startswith("ตอบไลน์") or q_lower.startswith("/reply-line"):
            return await self.handle_line_reply(q_clean)

        if q_lower in ("เปิดตอบอัตโนมัติ", "เปิด auto reply", "เปิด auto-reply", "/auto-reply on"):
            return await self.handle_line_toggle(True)

        if q_lower in ("ปิดตอบอัตโนมัติ", "ปิด auto reply", "ปิด auto-reply", "/auto-reply off"):
            return await self.handle_line_toggle(False)

        settings = __user__.get("valves")
        key = (
            settings.get("AITOB_API_KEY", "")
            if isinstance(settings, dict)
            else getattr(settings, "AITOB_API_KEY", "")
        )
        if not isinstance(key, str) or not key.strip():
            return "กรุณาตั้งค่า AITOB_API_KEY ของคุณใน User Valves ของ AItoB Assistant ก่อนใช้งาน หรือพิมพ์ 'เช็คไลน์' เพื่อดูกล่องข้อความ LINE"

        attached = __files__ if __files__ is not None else body.get("files", [])
        upload_requested = question.strip().lower() in (
            "ตรวจไฟล์ค่าใช้จ่าย",
            "ทำความสะอาดไฟล์",
            "/process-file",
        )
        if attached or upload_requested:
            if not upload_requested:
                return "สำหรับไฟล์แนบ กรุณาใช้คำสั่ง ตรวจไฟล์ค่าใช้จ่าย พร้อมแนบ CSV หรือ Excel หนึ่งไฟล์"
            try:
                return await process_attached_file(
                    self.valves.BASE_URL, key, __user__["id"], attached
                )
            except Exception:
                return (
                    "ยังประมวลผลไฟล์แนบไม่ได้ กรุณาตรวจส่วนเชื่อมไฟล์และบริการ Finance"
                )
        if question.strip().lower() in ("/download", "download csv", "ดาวน์โหลด csv"):
            try:
                return await fetch_export(self.valves.BASE_URL, key, __user__["id"])
            except Exception:
                return (
                    "ยังสร้างลิงก์ดาวน์โหลดไม่ได้ กรุณาตรวจส่วนเชื่อมไฟล์ของ Open WebUI"
                )
        history = []
        for item in messages[:index]:
            if (
                isinstance(item, dict)
                and item.get("role") in ("user", "assistant")
                and isinstance(item.get("content"), str)
                and item["content"].strip()
            ):
                history.append(
                    {"role": item["role"], "content": item["content"][:1000]}
                )
        history = history[-2:]

        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": "กำลังตรวจสิทธิ์และค้นข้อมูล…",
                        "done": False,
                    },
                }
            )
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(1250, connect=10), trust_env=False
            ) as client:
                response = await client.post(
                    self.valves.BASE_URL.rstrip("/") + "/chat",
                    headers={"Authorization": "Bearer " + key.strip()},
                    json={"question": question.strip(), "history": history},
                )
            errors = {
                401: "AItoB API key ไม่ถูกต้อง กรุณาตรวจ User Valves",
                403: "บัญชีนี้ไม่มีสิทธิ์ใช้งานคำขอนี้",
                409: "ระบบกำลังทำงานอีกคำขอหนึ่ง กรุณาลองใหม่เมื่อคำขอนั้นเสร็จ",
                400: "คำขอหรือประวัติแชตไม่อยู่ในรูปแบบที่รองรับ กรุณาเริ่มแชตใหม่",
            }
            if response.status_code != 200:
                return errors.get(
                    response.status_code,
                    "AItoB ทำงานไม่สำเร็จ กรุณาตรวจบริการบน Mac แล้วลองใหม่",
                )
            result = response.json()
            text = render_answer(result)
            if result.get("status") == "complete" and any(
                isinstance(item, dict) and item.get("id") == "finance-expenses"
                for item in result.get("sources", [])
            ):
                try:
                    text += "\n\n" + await fetch_export(
                        self.valves.BASE_URL, key, __user__["id"]
                    )
                except Exception:
                    text += "\n\nยังสร้างลิงก์ไฟล์ไม่ได้ พิมพ์ /download เพื่อลองใหม่"
            return text
        except (httpx.RequestError, ValueError):
            return "เชื่อมต่อ AItoB ไม่สำเร็จ กรุณาตรวจบริการพอร์ต 8002 บน Mac"
        finally:
            if __event_emitter__:
                await __event_emitter__(
                    {"type": "status", "data": {"description": "จบคำขอ", "done": True}}
                )
