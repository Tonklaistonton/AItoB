# AItoB — Private Local AI for Enterprise 🛡️

> **Sovereign Local AI Appliance** — ระบบ AI ส่วนตัวแบบ On-Premise ติดตั้งตรงถึงห้องเซิร์ฟเวอร์องค์กร ข้อมูลความลับไม่หลุดออกสู่อินเทอร์เน็ต 100% สอดคล้องตามมาตรฐาน PDPA

[![License: MIT](https://img.shields.io/badge/License-MIT-emerald.svg)](LICENSE)
[![Architecture: Air--Gapped](https://img.shields.io/badge/Security-Air--Gapped%20100%25-green.svg)](#security--architecture)
[![Local Inference](https://img.shields.io/badge/Latency-%3C%2025ms-cyan.svg)](#hardware-specification)
[![Python Test Suite](https://img.shields.io/badge/Tests-Passing-success.svg)](#testing)

---

## 📌 สารบัญ (Table of Contents)
- [ภาพรวมของโครงการ (Overview)](#ภาพรวมของโครงการ-overview)
- [จุดเด่นและคุณค่าหลัก (Value Propositions)](#จุดเด่นและคุณค่าหลัก-value-propositions)
- [โครงสร้างระบบและโมดูล (Project Architecture)](#โครงสร้างระบบและโมดูล-project-architecture)
- [เว็บไซต์และแอปพลิเคชันเฉพาะทาง (Dedicated Hubs)](#เว็บไซต์และแอปพลิเคชันเฉพาะทาง-dedicated-hubs)
- [วิดีโอสาธิตระบบ (Interactive Demo Video)](#วิดีโอสาธิตระบบ-interactive-demo-video)
- [การติดตั้งและเปิดใช้งาน (Getting Started)](#การติดตั้งและเปิดใช้งาน-getting-started)
- [การทดสอบความถูกต้อง (Testing)](#การทดสอบความถูกต้อง-testing)

---

## 🎯 ภาพรวมของโครงการ (Overview)

**AItoB** แก้ปัญหาคอขวดสำคัญขององค์กรธุรกิจที่ต้องการเร่งสปีดการทำงานด้วย AI แต่ติดข้อจำกัดด้านความมั่นคงปลอดภัย:
1. **ความลับรั่วไหลไม่ได้**: ฐานข้อมูลเงินเดือน งบการเงิน สัญญาลับ และข้อมูลส่วนบุคคล (PDPA) ไม่สามารถส่งขึ้น Public Cloud API
2. **งานเอกสารซ้ำซากกินเวลา**: งานกระทบยอดบิลภาษี ตรวจสัญญาหลายสิบหน้า คัดกรองเรซูเม่ กินเวลาพนักงานหลายร้อยชั่วโมงต่อเดือน
3. **ต้นทุนผันผวน**: ค่าบริการ Token Subscription บน Cloud พุ่งสูงตามปริมาณการใช้งาน

**AItoB Solution**: ให้บริการเครื่องฮาร์ดแวร์เซิร์ฟเวอร์ GPU สำเร็จรูป (Appliance) พร้อมติดตั้ง Local LLMs, ระบบเชื่อมโยงฐานข้อมูลภายใน (MCP/RAG) และระบบกำหนดสิทธิ์การเข้าถึง (Enterprise RBAC) ส่งมอบแบบ Turnkey พร้อมใช้งานในระบบปิด (Air-Gapped)

---

## ⚡ จุดเด่นและคุณค่าหลัก (Value Propositions)

- **Zero Cloud Egress**: ส่งออกข้อมูลสู่ภายนอก 0 KB การันตีในระดับสัญญานิติบุคคลและมี Audit Log เข้ารหัส SHA-256
- **฿0 Token API Bills**: ซื้อขาดฮาร์ดแวร์และค่าดูแลคงที่ ไม่มีค่าใช้จ่ายคิดตามจำนวน Token รายเดือน
- **Ultralow Latency**: ประมวลผลผ่าน LAN ในออฟฟิศ ตอบสนองรวดเร็วกว่า 25 ms
- **Human-in-the-Loop (HIL)**: AI ช่วยเตรียมข้อมูลและคัดกรองจุดเสี่ยง แต่การอนุมัติขั้นสุดท้ายยังคงอยู่ในการควบคุมของเจ้าหน้าที่จริง

---

## 📁 โครงสร้างระบบและโมดูล (Project Architecture)

```text
AItoB/
├── index.html          # หน้าหลัก: Pitch Deck, Simulator, ROI Calculator, Hubs
├── account.html        # เว็บแอปตรวจสลิปและบัญชีจริง (Standalone UI)
├── inbox.html          # เว็บแอปรวมแชท LINE OA & Gmail (Standalone UI)
├── finance.html        # เว็บไซต์เฉพาะทาง: แผนกบัญชีและการเงิน (Finance Hub)
├── hr.html             # เว็บไซต์เฉพาะทาง: แผนกทรัพยากรบุคคล (HR & RBAC Guard)
├── legal.html          # เว็บไซต์เฉพาะทาง: ฝ่ายจัดซื้อและสัญญา (Legal Scanner)
│
├── demo-video/         # วิดีโอจำลองระบบปฏิบัติการ Appliance (HyperFrames + GSAP)
│   ├── index.html      # 1080p Interactive Canvas Player พร้อมแผงควบคุมสด
│   └── package.json
│
├── ai-account/         # โมดูลระบบบัญชีและตรวจสลิป (Production Engine)
│   ├── server.js       # Node.js Native HTTP Server (Port 3001)
│   ├── lib/db.js       # ฐานข้อมูล node:sqlite พร้อมโหมด WAL
│   └── lib/vision.js   # โมดูลสกัดข้อความสลิป/บิล (OCR & Vision)
│
├── ai-chat/            # โมดูลตอบแชทลูกค้าอัตโนมัติ (Omni-Channel Engine)
│   ├── server.js       # Express Server + WebSocket (Port 3000)
│   ├── app/            # Next.js App Router (React UI)
│   └── lib/            # บริการ LINE Messaging API, Gmail SMTP, AI Routing
│
├── test_site.py        # Automated Test Suite (DOM & HTTP 200 Verification)
├── .gitignore          # ละเว้นโมเดล, ไพรเวทคีย์, ฐานข้อมูล, และ node_modules
└── README.md           # คู่มือเอกสารฉบับนี้
```

---

## 🏢 เว็บไซต์และแอปพลิเคชันเฉพาะทาง (Dedicated Hubs)

| แผนก / โมดูล | ไฟล์หน้าเว็บ | แอปพลิเคชันรันจริง | รายละเอียดความสามารถ |
| :--- | :--- | :--- | :--- |
| **ภาพรวมโครงการ** | `index.html` | - | Pitch Deck 6 สไลด์, เครื่องคำนวณ ROI แบบไดนามิก, เครื่องมือจำลองการทำงาน |
| **บัญชีและการเงิน** | `finance.html` | `account.html` / `ai-account` (Port 3001) | กระทบยอด 1,420 ใบเสร็จใน 1.8 วิ, ตรวจสอบสลิปซ้ำ (Duplicate Prevention) |
| **สื่อสาร & ลูกค้าสัมพันธ์** | `index.html` | `inbox.html` / `ai-chat` (Port 3000) | แชทรวมศูนย์ LINE OA & Gmail, ระบบ Claim/Release ส่งต่องานแอดมินคนจริง |
| **ทรัพยากรบุคคล (HR)** | `hr.html` | - | Enterprise RBAC Guard สกัดกั้นการดึงข้อมูลเงินเดือน, สอดคล้อง PDPA 100% |
| **จัดซื้อและนิติกรรมสัญญา** | `legal.html` | - | สแกนสัญญา 68 หน้า ชี้จุดเสี่ยงเพดานความรับผิดชอบ (Liability Cap) ใน 3.4 วิ |

---

## 🎬 วิดีโอสาธิตระบบ (Interactive Demo Video)

อยู่ในโฟลเดอร์ `demo-video/` พัฒนาด้วยเทคโนโลยี **HyperFrames Composition** ร่วมกับ **GSAP Timeline**:
- **Player HUD**: มีแถบเวลาสด Scrubber ลากข้ามฉาก, ปุ่ม Play/Pause, และปุ่มลัดเปลี่ยนฉาก
- **Web Audio FX**: ระบบเสียงเอฟเฟกต์สังเคราะห์ในตัวผ่าน Native Web Audio API
- **4 ฉากการทำงานจริง**:
  1. `00:00 - 00:05` : **Hardware Monitor** — เกจวัดโหลด 4x GPU และ Terminal Boot
  2. `00:05 - 00:10` : **Finance OCR** — ลำแสงเลเซอร์สแกนเนอร์และตัวเลขนับบิลวิ่งขึ้น 0 → 1,420 ใบ
  3. `00:10 - 00:15` : **HR RBAC Shield** — สกัดกั้นการแอบสืบค้นเงินเดือน พร้อมบันทึก Hash ป้องกันการแก้ไข
  4. `00:15 - 00:20` : **Legal Auto-Redline** — ไดอัลวัดความเสี่ยง 89% พร้อมแนะนำข้อความแก้ต่างอัตโนมัติ

---

## 🚀 การติดตั้งและเปิดใช้งาน (Getting Started)

### ความต้องการของระบบ (Requirements)
- **Node.js**: v22.0.0 หรือใหม่กว่า (รองรับ `node:sqlite`)
- **Python**: 3.9+ (สำหรับรัน Web Server และ Test Suite)

### 1. เปิดดูเว็บไซต์ทั้งหมด (Local Static Server)
```bash
# รัน HTTP Server ที่โฟลเดอร์โปรเจกต์
python3 -m http.server 8080

# เปิดเบราว์เซอร์เข้าชม:
# หน้าหลัก: http://localhost:8080/index.html
# แผนกบัญชี: http://localhost:8080/finance.html
# แผนก HR: http://localhost:8080/hr.html
# ฝ่ายจัดซื้อ/สัญญา: http://localhost:8080/legal.html
# ตรวจสลิปจริง: http://localhost:8080/account.html
# แชทรวมศูนย์จริง: http://localhost:8080/inbox.html
```

### 2. รันระบบบัญชีและตรวจสลิป (AIZEN Account Backend)
```bash
cd ai-account
node server.js
# Backend & UI จะเปิดทำงานที่ http://localhost:3001
```

### 3. รันระบบตอบแชทลูกค้าและกล่องข้อความรวม (AIZEN Responder)
```bash
cd ai-chat
npm ci
npm run dev
# Next.js App จะเปิดทำงานที่ http://localhost:3000
```

---

## 🧪 การทดสอบความถูกต้อง (Testing)

โปรเจกต์มีชุดทดสอบอัตโนมัติ `test_site.py` ครอบคลุมการตรวจ DOM Semantics, Section IDs, การเชื่อมโยงไฟล์ทั้งหมด และ HTTP 200 Response:

```bash
python3 -I test_site.py
```

ผลลัพธ์ที่คาดหวัง:
```text
✓ All HTML content and section assertions passed.
✓ HTTP 200 passed for index.html.
✓ HTTP 200 passed for finance.html.
✓ HTTP 200 passed for hr.html.
✓ HTTP 200 passed for legal.html.
✓ HTTP 200 passed for account.html.
✓ HTTP 200 passed for inbox.html.
✓ HTTP 200 passed for demo-video/index.html.
ALL CHECKS PASSED.
```

---

## 📄 ใบอนุญาต (License)
MIT License — พัฒนาและดูแลโดยทีมงาน **AItoB Sovereign AI Team**
