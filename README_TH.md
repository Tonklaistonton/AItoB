# AItoB Source สำหรับส่งงาน

ชุดนี้รวม source ปัจจุบันจาก Mac และโครงสร้างสำหรับติดตั้งใหม่ ดูคู่มือภาษาไทยแยกในหมวด Documents

## โครงสร้าง
- project/gateway: auth, ACL, keyword document retrieval, RAG, HTTP inference และ workflow CSV
- project/mcp-lab: agent, MCP tools, Assistant HTTP bridge และการรับ/ส่งออกค่าใช้จ่าย
- project/gmail-lab: Gmail OAuth, การตรวจเจ้าของ mailbox, ค้นหาและอ่านเฉพาะ label AItoB-Demo
- project/webui: Pipe v0.1.3 ที่ส่งออกจาก Open WebUI จริง ไม่ใช่ไฟล์รุ่นเก่าบนดิสก์
- project/open-webui: Compose ที่ตรึง image digest ของรุ่น 0.12.3
- project/services: template บริการ Gmail/Assistant ใช้ AITOB_LAB_ROOT
- tools: ตัวสร้าง config และ key ใหม่สำหรับเครื่องใหม่
- fixtures: ข้อมูลสังเคราะห์และ expected outputs
- tests: isolated upload tests ที่ใช้ stub auth ไม่ใช่ผล live HTTP
- evidence: ผลทดสอบที่มีขอบเขตและวันที่ในแต่ละรายงาน
- metadata: เวอร์ชันระบบ แพ็กเกจ และการปรับชุดส่ง
- reference/deployed_snapshot: source อ้างอิงจากเครื่องเดิม รวมสคริปต์เก่า ไม่ใช้เป็นลำดับติดตั้งใหม่

## ตรวจความครบถ้วน
python3 tools/verify_files.py
python3 -m unittest discover -s tests -v

## ก่อนติดตั้ง
ใช้เครื่องใหม่หรือสภาพแวดล้อมแยก ไม่คัดลอกทับ ~/aitob-lab ที่ใช้งานอยู่
อ่านคู่มือก่อนเรียก tools/prepare_local_config.py --lab <project-root>
ไม่รวม credentials เดิม ทุกเครื่องต้องสร้าง key และ WEBUI_SECRET_KEY ของตัวเอง
Gmail เป็นส่วนเสริม ต้องตั้ง EXPECTED_EMAIL และ OAuth ใหม่ ไม่ได้เปิดใช้กับอีเมลตัวอย่างโดยอัตโนมัติ
ติดตั้ง dependencies จาก registry/แหล่งทางการ ต้องใช้อินเทอร์เน็ตระหว่างเตรียมเครื่อง
Gemma4:12b ไม่รวม weights ใน ZIP ให้ดึงด้วย Ollama และตรวจ version/quantization ตามคู่มือ
เครื่องต้นแบบ Apple M5 24 GiB ไม่ใช่คำรับรอง capacity หรือ minimum สำหรับลูกค้าทั้งหมด

## สถานะการตรวจ
Source collection และ checksum ผ่าน ส่วนค่าใช้จ่ายมีผลทดสอบบน Mac/WebUI เดิม
โครงสร้างติดตั้งใหม่นี้ยังไม่ได้ทดสอบ end-to-end บนเครื่องว่าง จึงไม่อ้างว่า clean installation ผ่านแล้ว
อีเมลจริงและความลับไม่รวมอยู่ในชุดส่ง ต้องกำหนดข้อมูลเจ้าของและสิทธิ์ในเครื่องของผู้ติดตั้ง
ไม่รวมสำเนา source ของ Ollama/Open WebUI/Python/dependencies; ให้ติดตั้งจากผู้พัฒนาและตรวจเงื่อนไข license ของแต่ละรุ่น
