# Archived Development & Debug Scripts

โฟลเดอร์นี้รวบรวมสคริปต์เฉพาะกิจ (One-off / Ad-hoc scripts) ที่ใช้ในระหว่างขั้นตอนการพัฒนาและทดสอบระบบ Open WebUI และ LINE Integration โดยย้ายออกมาจากโฟลเดอร์หลัก `tools/` เพื่อความเป็นระเบียบเรียบร้อย

---

## สารบัญสคริปต์

### 1. การจัดการและตรวจสอบฐานข้อมูล (Database & Accounts)
- **`check_db.py`**: ตรวจสอบรายชื่อตารางทั้งหมดใน `webui.db` ภายใน container
- **`check_last.py`**: ดึงข้อมูลและข้อความแชทล่าสุดในโฟลเดอร์ `folder-line`
- **`inspect_auth.py`**: ตรวจสอบบัญชีผู้ใช้และค่า authentication hash ใน `auth` และ `user`
- **`clean_accounts.py`**: ล้างข้อมูลบัญชีผู้ใช้และแชทเก่า พร้อมเปิด `ui.enable_signup`
- **`reset_password.py`**: รีเซ็ตรหัสผ่านของผู้ดูแลระบบเป็นรหัสผ่านตั้งต้น
- **`fix_email.py`**: แก้ไขข้อผิดพลาดของอีเมลผู้ดูแลระบบ

### 2. การสร้าง Mock Data และจัดระเบียบหน้าตา (UI & Sidebar Mockup)
- **`organize_sidebar_timeline.py`**: สคริปต์จัดระเบียบหมวดหมู่โฟลเดอร์และสร้างแชทตัวอย่างตาม Timeline (Today, Yesterday, ตอบอีเมล, LINE)
- **`update_folders_and_sample.py`**: สคริปต์เวอร์ชันแรกในการสร้างเคสตัวอย่างสำหรับ LINE และโฟลเดอร์แชท

### 3. การทดสอบการทำงานของระบบ (Testing & Verification)
- **`test_pipe_utf8.py`**: ทดสอบการเรียกโมเดล AItoB Assistant Pipe ผ่าน REST API พร้อมตรวจสอบการประมวลผลภาษาไทย (UTF-8)
- **`test_admin_reply.py`**: ทดสอบการส่งคำสั่งแอดมินตอบแชทลูกค้า (`ส่งเลย`, `ปิดเคส`)
- **`test_full_cycle.py`**: ทดสอบวงจรการทำงานแบบครบวงจร (จำลองข้อความ LINE เข้ามา -> บันทึก DB -> แอดมินตอบ)

### 4. สคริปต์แพตช์และอัปเดตโมดูล (Patch & Direct DB Updates)
- **`patch_main_py.py`**: สคริปต์แพตช์เพิ่ม Endpoint ภายใน `/api/internal/line-message` ใน Open WebUI backend
- **`patch_webui_main.py`**: สคริปต์แพตช์เพิ่ม Reverse Proxy `/line-proxy/api` ใน Open WebUI backend
- **`register_line_tool.py`**: สคริปต์ลงทะเบียน LINE Tool ลงในฐานข้อมูล Open WebUI โดยตรง
- **`update_tool.py`**: สคริปต์อัปเดตโค้ดของ LINE Tool ในฐานข้อมูล
- **`update_pipe_in_db.py`**: สคริปต์อัปเดตโค้ด AItoB Function Pipe ลงในฐานข้อมูล
- **`find_workspace.py`**: สคริปต์ค้นหา Element ID ภายในไฟล์ Javascript bundle ของ frontend
