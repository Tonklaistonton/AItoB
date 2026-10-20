"""
title: AItoB Assistant
author: AItoB Lab
version: 0.1.0
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
        if (not isinstance(source_id, str)
                or re.fullmatch(r"[A-Za-z0-9_-]{1,128}", source_id) is None
                or source_id in seen):
            continue
        seen.add(source_id)
        title = source.get("title") or source.get("subject") or source_id
        note = " — ใช้ข้อความบางส่วน" if source.get("truncated") else ""
        lines.append("- " + safe_text(title) + " `[" + source_id + "]`" + note)
    if lines:
        text += "\n\n**แหล่งข้อมูลที่ระบบใช้**\n\n" + "\n".join(lines)
    return text


class Pipe:
    class Valves(BaseModel):
        BASE_URL: str = Field(default="http://host.docker.internal:8002",
                              description="AItoB Assistant service URL; configured by administrator")

    class UserValves(BaseModel):
        AITOB_API_KEY: str = Field(
            default="", description="Your own AItoB API key; never enter it in a chat message",
            json_schema_extra={"input": {"type": "password"}}
        )

    def __init__(self):
        self.valves = self.Valves()

    def pipes(self):
        return [{"id": "assistant", "name": "AItoB Assistant"}]

    async def pipe(self, body: dict, __user__: dict = None,
                   __event_emitter__=None, __task__: str = None):
        # Never execute business operations for title/tag/background generation.
        if __task__ is not None:
            return ""
        if not isinstance(__user__, dict) or not __user__.get("id"):
            return "กรุณาลงชื่อเข้าใช้ก่อนใช้งาน AItoB"
        settings = __user__.get("valves")
        key = settings.get("AITOB_API_KEY", "") if isinstance(settings, dict) else getattr(settings, "AITOB_API_KEY", "")
        if not isinstance(key, str) or not key.strip():
            return "กรุณาตั้งค่า AITOB_API_KEY ของคุณใน User Valves ของ AItoB Assistant ก่อนใช้งาน"

        messages = body.get("messages", [])
        if not isinstance(messages, list):
            return "รูปแบบข้อความไม่ถูกต้อง"
        user_indices = [index for index, item in enumerate(messages)
                        if isinstance(item, dict) and item.get("role") == "user"]
        if not user_indices:
            return "กรุณาพิมพ์คำถาม"
        index = user_indices[-1]
        question = messages[index].get("content")
        if not isinstance(question, str) or not 1 <= len(question.strip()) <= 1000:
            return "กรุณาส่งคำถามแบบข้อความ ความยาวไม่เกิน 1,000 ตัวอักษร"
        history = []
        for item in messages[:index]:
            if (isinstance(item, dict) and item.get("role") in ("user", "assistant")
                    and isinstance(item.get("content"), str) and item["content"].strip()):
                history.append({"role": item["role"], "content": item["content"][:1000]})
        history = history[-2:]

        if __event_emitter__:
            await __event_emitter__({"type": "status", "data": {"description": "กำลังตรวจสิทธิ์และค้นข้อมูล…", "done": False}})
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(1250, connect=10), trust_env=False) as client:
                response = await client.post(
                    self.valves.BASE_URL.rstrip("/") + "/chat",
                    headers={"Authorization": "Bearer " + key.strip()},
                    json={"question": question.strip(), "history": history}
                )
            errors = {
                401: "AItoB API key ไม่ถูกต้อง กรุณาตรวจ User Valves",
                403: "บัญชีนี้ไม่มีสิทธิ์ใช้งานคำขอนี้",
                409: "ระบบกำลังทำงานอีกคำขอหนึ่ง กรุณาลองใหม่เมื่อคำขอนั้นเสร็จ",
                400: "คำขอหรือประวัติแชตไม่อยู่ในรูปแบบที่รองรับ กรุณาเริ่มแชตใหม่",
            }
            if response.status_code != 200:
                return errors.get(response.status_code, "AItoB ทำงานไม่สำเร็จ กรุณาตรวจบริการบน Mac แล้วลองใหม่")
            return render_answer(response.json())
        except (httpx.RequestError, ValueError):
            return "เชื่อมต่อ AItoB ไม่สำเร็จ กรุณาตรวจบริการพอร์ต 8002 บน Mac"
        finally:
            if __event_emitter__:
                await __event_emitter__({"type": "status", "data": {"description": "จบคำขอ", "done": True}})
