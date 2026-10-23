# AItoB

ระบบต้นแบบ Local AI สำหรับองค์กร ใช้ Ollama และ Gemma4:12b ร่วมกับ Open WebUI เพื่อช่วยค้นและสรุปข้อมูลภายใน สรุปอีเมล และตรวจไฟล์ค่าใช้จ่าย โดยตรวจสิทธิ์การใช้เครื่องมือที่ backend

## เอกสารภาษาไทย

- [รายงานโครงการและแผนบริษัท (PDF)](docs/AItoB_รายงานโครงการและแผนบริษัท.pdf)
- [คู่มือติดตั้งและใช้งาน (PDF)](docs/AItoB_คู่มือติดตั้งและใช้งาน.pdf)
- [คู่มือฉบับข้อความ](docs/คู่มือติดตั้งและใช้งาน.md)
- [คำสั่งสำหรับคัดลอก แยก Mac และ Windows](docs/installation_commands.txt)
- [รายละเอียด source และสถานะการตรวจ](README_TH.md)

## เริ่มต้น

อ่านคู่มือติดตั้งก่อนเริ่ม เตรียม Mac Apple Silicon, Python 3.12, Ollama และ Docker Desktop แล้วตรวจไฟล์จากโฟลเดอร์ repository:

```sh
python3 tools/verify_files.py
python3 -m unittest discover -s tests -v
```

ใช้เครื่องใหม่หรือสภาพแวดล้อมแยก ไม่คัดลอกทับระบบที่กำลังใช้งาน สร้าง config และ key ใหม่ด้วยเครื่องมือใน `tools` ตามคู่มือ ส่วน Gmail ต้องกำหนดเจ้าของและ OAuth ด้วยตนเอง

## โครงสร้างหลัก

| โฟลเดอร์ | หน้าที่ |
|---|---|
| `project/gateway` | ตรวจ key และสิทธิ์ ค้นข้อมูล และเรียกโมเดล |
| `project/mcp-lab` | เครื่องมือ Assistant และการนำเข้า/ส่งออกค่าใช้จ่าย |
| `project/gmail-lab` | OAuth และการค้น/อ่านอีเมลตามขอบเขตแอป |
| `project/webui` | Pipe สำหรับ Open WebUI |
| `project/open-webui`, `project/services` | การตั้งค่าบริการ |
| `fixtures`, `tests` | ข้อมูลสังเคราะห์และชุดทดสอบแยกส่วน |
| `evidence`, `metadata` | หลักฐานพร้อมขอบเขตและข้อมูลเวอร์ชัน |
| `reference` | source อ้างอิงเดิม ไม่ใช่ลำดับติดตั้งใหม่ |

## สถานะและขอบเขต

ผลบนเครื่องต้นแบบตรวจค่าใช้จ่าย 6 แถว ได้ 3 แถวที่ผ่าน 1 แถวซ้ำ 2 แถวปฏิเสธ ยอดรวม 2,000.00 บาท ชุดทดสอบแยกส่วนมี 10 กรณีและใช้สิทธิ์จำลอง ดูรายละเอียดและวันที่ใน `evidence`

การติดตั้งใหม่ครบวงจรบน Mac ว่าง จำนวนผู้ใช้พร้อมกัน และการซ้อมกู้คืนยังไม่ยืนยันครบ ชื่อบัญชี WebUI ยังไม่ผูกกับตัวตน gateway แบบครบวงจร

## ข้อมูลลับและส่วนประกอบภายนอก

Repository นี้ใช้ source ที่ตรวจและแทนค่าลับแล้ว ไม่มี key, OAuth token, ฐานข้อมูลผู้ใช้ หรืออีเมลจริง ไม่รวม model weights หรือ Docker images ต้องติดตั้งส่วนประกอบภายนอกจากผู้พัฒนาและตรวจ license ของแต่ละส่วน ฟอนต์ Kanit มีไฟล์ OFL แนบใน `docs/fonts/Kanit`

---

## การพัฒนาต่อยอดสู่ระดับ Production และ GitHub (Universal & Extensible Update)

เพื่อให้นำระบบไปต่อยอด ใช้งานบนเครื่องอื่น (Windows, Linux, macOS) หรือนำขึ้น GitHub และ Cloud ได้อย่างปลอดภัย ได้มีการปรับปรุงสถาปัตยกรรมเพิ่มเติมดังนี้:

### 1. สถาปัตยกรรมแบบ Universal Docker Compose (`compose.yaml`)
- **Containerized Gateway:** รวม Gateway Service เข้ามาเป็นคอนเทนเนอร์ ไม่ต้องพึ่งพา macOS LaunchAgent
- **Internal Docker Network (`aitob-net`):** ทุก Service สื่อสารกันผ่าน Internal DNS (`gateway:8000`, `assistant:8002`, `gmail:8001`) ป้องกันการเปิดพอร์ต Backend สู่ภายนอก
- **Named Volumes:** ใช้ Docker Named Volumes (`webui-data`, `gmail-credentials`, `finance-data`) เพื่อตัดการพึ่งพา Absolute Path ของเครื่องเดิม

### 2. ความยืดหยุ่นของโมเดล AI (Multi-Provider Support)
สามารถเลือกเชื่อมต่อโมเดลได้ตามความเหมาะสมผ่านไฟล์ `.env`:
- **Anthropic Claude API:** เช่น `claude-3-5-sonnet` สำหรับคำตอบที่แม่นยำสูง
- **OpenAI / OpenRouter API:** เช่น `gpt-4o`
- **Local Ollama:** เช่น `gemma4:12b` สำหรับการประมวลผลภายในองค์กร (On-premise)

### 3. การยกระดับความปลอดภัย (Security Hardening)
- **CIS Docker Benchmark v1.8.0:** คอนเทนเนอร์ทั้งหมดทำงานด้วยสิทธิ์ Non-root (`UID 10001:10001`), ตัดสิทธิ์ที่ไม่จำเป็นด้วย `cap_drop: ALL`, เปิดใช้ `no-new-privileges: true`, ล็อก Root Filesystem เป็น `read_only: true` และจำกัดการใช้ CPU/RAM
- **GitHub Secret Protection & CI/CD:** เพิ่ม GitHub Actions ([`security.yml`](.github/workflows/security.yml)) เพื่อรัน **Gitleaks** ตรวจจับ Secret รั่วไหล และ Hadolint ตรวจสอบ Dockerfile อัตโนมัติทุกครั้งที่มีการ Commit/Push

---

### วิธีเริ่มต้นใช้งานฉบับย่อ (Quick Start)

#### ทางเลือกที่ 1: Docker Compose (สำหรับ Mac / Linux / Docker Desktop)

1. **คัดลอกไฟล์ตั้งค่า Environment:**
   ```bash
   cp .env.example .env
   ```
2. **แก้ไข `.env`:** ระบุ API Key และกำหนด `WEBUI_SECRET_KEY` ตามต้องการ
3. **เริ่มระบบด้วยคำสั่งเดียว:**
   ```bash
   docker compose up -d
   ```
4. **เปิดใช้งาน:** เข้าหน้าเว็บ Open WebUI ที่ `http://localhost:3000`

#### ทางเลือกที่ 2: รันผ่าน WSLC โดยตรง (สำหรับ Windows 11 ที่มี WSL Container CLI)

หากต้องการรันด้วย `wslc.exe` โดยตรงโดยไม่ต้องติดตั้ง Docker Desktop:

```powershell
# เริ่มระบบทั้งหมด
.\tools\wslc-stack.ps1 start

# ตรวจสอบสถานะคอนเทนเนอร์
.\tools\wslc-stack.ps1 status

# ดู Logs
.\tools\wslc-stack.ps1 logs webui

# หยุดระบบ
.\tools\wslc-stack.ps1 stop
```
