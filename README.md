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

## การรันด้วย Docker (Local AI 100% via Ollama)

Branch นี้ถูกตั้งค่าให้ทำงานแบบ **Private Local AI 100%** ผ่าน **Ollama** โดยไม่มีการเชื่อมต่อ Cloud API ภายนอก

### สถาปัตยกรรมบริการ
- **Ollama:** ประมวลผลโมเดล Local ภายในเครื่อง (Default: `gemma4:12b`)
- **Gateway:** ควบคุมสิทธิ์และทำหน้าที่เป็น Proxy ไปยัง Ollama ภายใน Container Network
- **Assistant:** ให้บริการ MCP Tools, ค้นเอกสาร และประมวลผลงาน
- **Gmail Backend:** ให้บริการค้นหาและอ่านอีเมลเฉพาะขอบเขต
- **Open WebUI:** หน้าบ้านสำหรับแชต เชื่อมต่อกับ Ollama โดยตรง

---

### วิธีเริ่มต้นใช้งาน (Quick Start)

1. **เตรียมไฟล์ Environment:**
   ```bash
   cp .env.example .env
   ```
2. **เริ่มระบบทั้งหมดด้วย Docker:**
   ```bash
   docker compose up -d
   ```
3. **ดึงโมเดล Local (ครั้งแรก):**
   ```bash
   docker exec -it aitob-ollama ollama pull gemma4:12b
   ```
4. **เข้าใช้งาน:** เปิดเบราว์เซอร์ไปที่ `http://localhost:3000`
