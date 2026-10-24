# AItoB Project Guidelines

AItoB is an enterprise-grade, per-user authenticated local AI system integrating Ollama/Cloud LLMs with Open WebUI, custom security gateways, Gmail integration, and expense document validation.

---

## Architecture Overview

| Directory | Role | Runtime / Port |
| :--- | :--- | :--- |
| `project/gateway` | Token auth, policy enforcement, RAG search & summarizer | Python FastAPI / Port 8000 (Internal) |
| `project/gmail-lab` | Gmail OAuth, search & read boundary service | Python / Port 8001 (Internal) |
| `project/mcp-lab` | Assistant service, MCP tools, finance upload & export | Python / Port 8002 (Internal) |
| `project/webui` | Open WebUI Pipe function, custom CSS & JS loader | Port 3000 -> 8080 |
| `tools/` | Active maintenance, asset deployer & stack scripts | PowerShell & Python |
| `tools/archive/` | Historical/debug/test scripts kept for reference | Python |
| `tests/` | Isolated unit tests | Python `unittest` |
| `fixtures/` | Synthetic data fixtures for validation | Excel, CSV |

---

## Common Commands

### 1. Running Unit Tests
```sh
# Run all isolated unit tests
python -m unittest discover tests -v

# Verify project file integrity
python tools/verify_files.py
```

### 2. Container Stack Management (Windows / WSLC)
```powershell
# Start all services
.\tools\wslc-stack.ps1 start

# Check container status
.\tools\wslc-stack.ps1 status

# View service logs
.\tools\wslc-stack.ps1 logs webui
.\tools\wslc-stack.ps1 logs gateway

# Stop all services
.\tools\wslc-stack.ps1 stop

# Re-apply WebUI custom assets (CSS & JS loader)
.\tools\apply-webui-assets.ps1
```

### 3. Container Stack Management (Docker Compose)
```sh
# Start stack with Docker Compose
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f webui
```

---

## Security & Engineering Standards

1. **Secrets Management:**
   - **NEVER** commit API keys, tokens, passwords, or personal credentials into git.
   - All sensitive configurations must be provided via environment variables in `.env` (derived from `.env.example`).
   - Repository runs Gitleaks in CI (`.github/workflows/security.yml`).

2. **Container Security (CIS Docker Benchmark):**
   - Run containers as non-root (`UID 10001:10001`).
   - Drop all Linux capabilities (`cap_drop: ALL`).
   - Enforce `no-new-privileges: true` and `read_only: true` with explicitly sized `tmpfs`.
   - Limit CPU and memory in `compose.yaml`.

3. **Authentication & Trust Boundaries:**
   - Always fail-closed on signature checks or missing authentication headers.
   - Validate and sanitize all external user inputs at service boundaries.
   - Never expose raw backend services (`gateway`, `gmail`, `assistant`) directly to external networks; keep them on the internal Docker network (`aitob-net`).

4. **WebUI Pipe & Static Assets:**
   - Active Pipe function is maintained at `project/webui/aitob_openwebui_pipe.py`.
   - Custom UI styles and Onboarding Wizard are at `project/webui/custom.css` and `project/webui/loader.js`.
   - Ensure UTF-8 byte preservation when deploying assets to containers (use `tools/deploy_assets.py`).

5. **Code Style & Simplicity:**
   - Keep diffs focused and minimal.
   - Use standard library first where applicable.
   - Keep scratchpad/one-off test scripts in `tools/archive/` instead of cluttering the root or active `tools/` folder.

---

## สิ่งที่ดำเนินการเสร็จสิ้นแล้ว (Completed Milestones)

### 1. ระบบโครงสร้างพื้นฐานและความปลอดภัยคอนเทนเนอร์ (Container & Hardening)
- [x] ออกแบบ `compose.yaml` รองรับสถาปัตยกรรมแบบ Microservices และเชื่อมต่อผ่าน Internal Network (`aitob-net`)
- [x] ยกระดับความปลอดภัยตาม **CIS Docker Benchmark v1.8.0**:
  - รันทุก Service ด้วย Non-root (`UID 10001:10001`)
  - ตัด Linux Capabilities ทั้งหมด (`cap_drop: ALL`)
  - ล็อก Root Filesystem เป็น `read_only: true` และเปิด `no-new-privileges: true`
  - กำหนด `tmpfs` พร้อมขนาดและ flags ที่ปลอดภัยสำหรับพื้นที่เขียนชั่วคราว
  - ตั้งค่าจำกัดทรัพยากร CPU และ Memory
- [x] พัฒนา `tools/wslc-stack.ps1` สำหรับบริหารจัดการ Stack บน Windows 11 ผ่าน `wslc.exe` โดยไม่ต้องพึ่ง Docker Desktop
- [x] ติดตั้ง CI/CD Security Workflow (`.github/workflows/security.yml`) พร้อม Gitleaks และ Hadolint

### 2. เซอร์วิสหลักและระบบ AI Backend (Core Services & AI Lab)
- [x] **Gateway (`project/gateway`)**: ตรวจสอบสิทธิ์ (Token Auth), บังคับใช้นโยบายความปลอดภัย, และเชื่อมต่อ LLM/RAG
- [x] **Gmail Lab (`project/gmail-lab`)**: ระบบ OAuth สำหรับค้นหาและอ่านอีเมลตามขอบเขตความปลอดภัย
- [x] **Assistant MCP (`project/mcp-lab`)**: เครื่องมือตรวจสอบไฟล์ค่าใช้จ่าย (Expense CSV/XLSX) และส่งออกข้อมูล
- [x] ชุดทดสอบ Isolated Unit Tests (`tests/test_finance_upload.py`) ผ่านสมบูรณ์ (10/10 เคส)

### 3. Open WebUI Customization & Frontend Integration
- [x] พัฒนา **AItoB Assistant Pipe Function** (`project/webui/aitob_openwebui_pipe.py`) เชื่อมต่อ Open WebUI เข้ากับ Gateway
- [x] ปรับแต่งส่วนติดต่อผู้ใช้ด้วย Onboarding Wizard (`project/webui/loader.js` และ `project/webui/custom.css`):
  - โมดอลตั้งค่าการเชื่อมต่อแบบ 2x2 Services (Database, n8n, LINE, Gmail)
  - กล่องคำสั่งลัด Quick Prompts Accordion (Finance, Travel Policy, Email RAG)
- [x] พัฒนาระบบ Deploy Asset แบบไบนารีที่รักษารหัสภาษาไทย UTF-8 (`tools/deploy_assets.py`, `tools/apply-webui-assets.ps1`)

### 4. การจัดระเบียบโค้ดและการตรวจสอบความปลอดภัย (Cleanup & Security Audit)
- [x] จัดระเบียบโฟลเดอร์ `tools/` ย้ายสคริปต์เฉพาะกิจ/ทดสอบ 17 ไฟล์ไปไว้ที่ `tools/archive/` พร้อมสารบัญ `tools/archive/README.md`
- [x] ลบไฟล์ทดสอบซ้ำซ้อนใน root และ `tools/`
- [x] ดำเนินการ Security Audit และปิดการทำงานของ `line-bot` service ออกจาก Running Stack ชั่วคราวเพื่อรอการ Hardening
- [x] จัดทำเอกสารคู่มือมาตรฐานโครงการ `CLAUDE.md`

