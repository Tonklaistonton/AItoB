# AItoB: Enterprise Local AI & LINE Assistant Platform

> **Language / ภาษา:** [English](../README.md) | **ภาษาไทย**

ระบบปัญญาประดิษฐ์ต้นแบบระดับองค์กร (Enterprise-grade Local AI System) ที่เน้นความปลอดภัย ความเป็นส่วนตัวของข้อมูล (Data Privacy) และการยืนยันตัวตนรายบุคคล (Per-user Authentication) เชื่อมต่อระหว่างโมเดลภาษา (Ollama / Cloud LLM), Open WebUI, ระบบคัดกรองเอกสารภายใน, Gmail และ LINE Official Account ภายใต้การควบคุมแบบ **Human-in-the-Loop (HITL)**

---

## สถาปัตยกรรมและฟีเจอร์หลัก (Key Features)

### 1. Security Gateway & Role-Based RAG (`project/gateway`)
- **Per-User Token Authentication:** ยืนยันตัวตนด้วย Bearer Token แบบ Fail-Closed
- **Permission Boundary Search:** กรองเอกสารตามสังกัดทีม (HR, Finance) และสิทธิ์ (Role) *ก่อน* ส่งข้อมูลให้โมเดลประมวลผล
- **Prompt Injection Defense:** ป้องกันคำสั่งแทรกซ้อนในเอกสารหรืออีเมล และบังคับให้อ้างอิงรหัสต้นทาง เช่น `[hr-leave]`, `[finance-budget]`

### 2. Expense Document Validation & Cleaner (`project/mcp-lab`)
- **Memory-Bounded Processing:** ประมวลผลไฟล์ CSV และ Excel (`.xlsx`) ในหน่วยความจำโดยไม่เขียนทับไฟล์ระบบ
- **Formula Injection Defense:** ตรวจจับและปฏิเสธข้อมูลที่ขึ้นต้นด้วย `=`, `+`, `-`, `@` หรือ ASCII Control Characters
- **Strict Decimal Arithmetic:** คำนวณยอดเงินและปัดเศษด้วย `decimal.Decimal` ทศนิยม 2 ตำแหน่ง ป้องกันปัญหา Floating-point inaccuracies

### 3. Bounded Gmail Integration (`project/gmail-lab`)
- **Owner Scope Boundary:** จำกัดการเข้าถึงเฉพาะกล่องข้อความของผู้ใช้ที่ได้รับอนุญาต
- **Safe Truncation:** ตัดทอนเนื้อหาอีเมลตามขีดจำกัดเพื่อป้องกัน Context Window Overflow และระบุสถานะเนื้อหาถูกตัดทอนชัดเจน

### 4. LINE Official Account & Human-in-the-Loop Inbox (`project/line-bot`)
- **HMAC-SHA256 Webhook Verification:** ตรวจลายเซ็น `X-Line-Signature` ทุกคำขอแบบ Constant-time
- **AI Draft Generation:** ดึงคำถามจากลูกค้าให้ผู้ช่วย AI ช่วยร่างคำตอบเบื้องต้น
- **Direct SQLite Sync:** นำเข้าบทสนทนาเข้าฐานข้อมูล Open WebUI (`webui.db`) โดยตรงแยกโฟลเดอร์ `💬 แชทลูกค้า LINE`
- **HITL Outbound Push:** แอดมินสามารถตรวจสอบ ปรับแก้คำตอบ และกดส่งผ่าน Open WebUI เข้า LINE ลูกค้าได้ทันที

### 5. CIS Docker Benchmark Hardening (`compose.yaml`)
- **Non-Root Execution:** ทุกคอนเทนเนอร์ทำงานด้วย `UID 10001:10001`
- **Principle of Least Privilege:** บังคับใช้ `no-new-privileges: true` และ `cap_drop: ALL`
- **Immutability:** กำหนด Root Filesystem เป็น `read_only: true` พร้อม `tmpfs` ที่มีแฟล็ก `noexec,nosuid`
- **Internal Network Isolation:** ทุก Microservice สื่อสารกันผ่านเน็ตเวิร์กภายใน `aitob-net` ไม่เปิดพอร์ต Backend ออกภายนอก

---

## ตารางบริการในระบบ (Service Map)

| Service | Directory | Internal Port | Host Port | Runtime / Framework | หน้าที่รับผิดชอบ |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **webui** | `project/open-webui` | `8080` | `3000` | Open WebUI (Node/Python) | หน้าต่างแชทหลัก, Custom CSS & JS Loader |
| **gateway** | `project/gateway` | `8000` | `8000` | Python 3.12 (HTTP Server) | Token Auth, RAG Search, Policy Enforcement |
| **assistant** | `project/mcp-lab` | `8002` | `8002` | Python 3.12 (Threading HTTP) | Unified Agent, MCP Tools, Finance Upload |
| **gmail** | `project/gmail-lab` | `8001` | `8001` | Python 3.12 (HTTP Server) | Gmail OAuth & Read Boundary API |
| **line-bot** | `project/line-bot` | `8003` | `8003` | Python 3.12 (Threading HTTP) | LINE Webhook Receiver, SQLite Sync, Push API |

---

## โครงสร้างไดเรกทอรี (Repository Layout)

```
AItoB/
├── .github/workflows/       # CI/CD: Gitleaks Scan & Automated Tests
├── compose.yaml             # Universal Docker Compose (CIS Hardened)
├── docs/                    # รายงานโครงการ แผนธุรกิจ คู่มือ Kanit PDF และ ADR
│   ├── adr/                 # Architecture Decision Records (e.g. LINE Webhook HITL)
│   └── fonts/               # ฟอนต์ Kanit พร้อมสัญญาอนุญาต OFL
├── evidence/                # ข้อมูลและผลการตรวจสอบความปลอดภัยย้อนหลัง
├── fixtures/                # ข้อมูลทดสอบสังเคราะห์ (Excel, CSV)
├── project/
│   ├── gateway/             # Auth, Search, RAG, Workflow
│   ├── gmail-lab/           # Gmail Integration
│   ├── line-bot/            # LINE Official Account Service
│   ├── mcp-lab/             # Assistant Service & Finance Validation
│   └── webui/               # Open WebUI Pipe (aitob_openwebui_pipe.py), CSS & JS
├── tests/                   # Isolated Unit Tests & Self-checks
├── tools/                   # สคริปต์บริหารจัดการ Container, Asset Deployer
│   └── archive/             # สคริปต์ประวัติศาสตร์/Debug เก็บไว้อ้างอิง
├── .env.example             # เทมเพลตตัวแปรสภาพแวดล้อม
└── READMEfix.md             # เอกสารฉบับปรับปรุงนี้
```

---

## วิธีเริ่มต้นใช้งาน (Quick Start)

### ข้อกำหนดเบื้องต้น (Prerequisites)
- Docker Desktop หรือ WSL Container CLI (`wslc.exe`)
- Python 3.12 ขึ้นไป
- Local Ollama (รัน `ollama run gemma4:12b`) หรือ Cloud API Key (OpenAI / Anthropic)

### ขั้นตอนที่ 1: ตั้งค่าสภาพแวดล้อม (.env)
คัดลอกไฟล์ `.env.example` เป็น `.env` และกำหนดค่า:
```sh
cp .env.example .env
```
กำหนดค่าสำคัญใน `.env`:
```ini
OPENWEBUI_PORT=3000
GATEWAY_PORT=8000
GMAIL_PORT=8001
ASSISTANT_PORT=8002
LINE_BOT_PORT=8003

# โมเดล LLM
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=gemma4:12b

# กุญแจความปลอดภัย (สุ่ม base64 32 bytes)
WEBUI_SECRET_KEY=your_generated_random_secret_key
WEBUI_AUTH=true

# LINE Integration (ถ้ามี)
LINE_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token
LINE_CHANNEL_SECRET=your_line_channel_secret
```

### ขั้นตอนที่ 2: เริ่มต้นระบบ

#### ตัวเลือก A: ใช้งานผ่าน Docker Compose (มาตรฐาน)
```sh
# เริ่มต้น Stack ทั้งหมด
docker compose up -d

# ตรวจสอบสถานะการทำงาน
docker compose ps

# ดูบันทึกการทำงาน (Logs)
docker compose logs -f gateway
docker compose logs -f line-bot
```

#### ตัวเลือก B: ใช้งานผ่าน WSLC บน Windows 11
```powershell
# เริ่มการทำงานของ Stack และ Deploy Custom Assets อัตโนมัติ
.\tools\wslc-stack.ps1 start

# ตรวจสอบสถานะ
.\tools\wslc-stack.ps1 status

# ดู Logs
.\tools\wslc-stack.ps1 logs webui

# หยุดการทำงาน
.\tools\wslc-stack.ps1 stop
```

### ขั้นตอนที่ 3: เข้าใช้งาน
- **Open WebUI:** เข้าผ่านเบราว์เซอร์ที่ [http://localhost:3000](http://localhost:3000)
- **LINE Webhook Endpoint:** กำหนด Webhook URL ใน LINE Developers Console ไปที่ `https://<your-domain>/webhook` (พอร์ตภายใน 8003)

---

## การทดสอบความถูกต้องและความปลอดภัย (Testing & Verification)

รันชุดทดสอบแยกส่วน (Unit Tests) เพื่อตรวจสอบความถูกต้องของสิทธิ์การเข้าถึงและความปลอดภัย:

```sh
# รัน Unit Tests ทั้งหมดใน tests/
python -m unittest discover tests -v

# รัน Self-Check สำหรับ LINE Bot Signature & Admin Auth
python tests/test_line_service.py
```

### มาตรฐานความปลอดภัย (Security Standards)
1. **Secrets Management:** ห้าม commit API Key, Token, Password หรือไฟล์ `.key` ลงใน Git เด็ดขาด (มี Gitleaks ตรวจจับใน GitHub CI)
2. **Fail-Closed Principle:** ทุกฟังก์ชันตรวจสอบสิทธิ์ หากพบข้อผิดพลาด ลายเซ็นไม่ตรง หรือไม่มี Token จะปฏิเสธคำขอทันที (HTTP 401/403)
3. **Spreadsheet Security:** ห้ามรันสูตรหรือคำนวณไฟล์ภายนอกโดยไม่ผ่านการ Sanitization

---

## เอกสารอ้างอิงเพิ่มเติม (References)

- [คู่มือติดตั้งและใช้งานฉบับเต็ม (PDF)](docs/AItoB_คู่มือติดตั้งและใช้งาน.pdf)
- [รายงานโครงการและแผนบริษัท (PDF)](docs/AItoB_รายงานโครงการและแผนบริษัท.pdf)
- [ADR 0001: LINE Webhook Integration via Direct SQLite & HITL](docs/adr/0001-line-webui-human-in-the-loop.md)
- [คำศัพท์เทคนิคและนิยามสถาปัตยกรรม (GLOSSARY.md)](GLOSSARY.md)
- [แนวทางการพัฒนาและคำสั่งประจำ (CLAUDE.md)](CLAUDE.md)
