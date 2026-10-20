# AItoB lab — คู่มือดูแลระบบ

สถานะที่ตรวจผ่าน 18 ตุลาคม 2026: reboot Mac แล้วล็อกอินบัญชี lab, บริการทั้งห้ากลับมาเอง, CSV และ Gmail ทำงานผ่านแชตได้ หลังติดตั้ง LaunchAgents และ Docker Compose

## 1. ระบบปัจจุบัน

Windows Browser → SSH tunnel/Tailscale → Open WebUI → Assistant Service → Gateway/LLM และ MCP tools → เอกสาร, CSV, Gmail backend

| บริการ | ตำแหน่งที่รับคำขอบน Mac | วิธีดูแล process |
|---|---|---|
| Ollama / gemma4:12b | 127.0.0.1:11434 | LaunchAgent: com.aitob.lab.ollama |
| Gateway | 127.0.0.1:8000 | LaunchAgent: com.aitob.lab.gateway |
| Gmail backend | 127.0.0.1:8001 | Compose ใน ~/aitob-lab/services |
| Assistant | 127.0.0.1:8002 | Compose ใน ~/aitob-lab/services |
| Open WebUI | 127.0.0.1:3000 | Compose ใน ~/aitob-lab/open-webui |

Mac: M5 / 24 GiB. บัญชี lab: ai-dev-for-devtomoon. Gateway ใช้ /usr/bin/python3; MCP และ Gmail ใช้ Python ใน Docker ไม่ติดตั้ง SDK เพิ่มลง Python ของ Mac

## 2. เปิดใช้งานตามปกติ

1. เปิด Mac และล็อกอินหน้า macOS ด้วยบัญชี lab ข้างต้น รอ Docker Desktop พร้อม
2. LaunchAgents เริ่ม Ollama และ Gateway; Docker เริ่ม container ที่ไม่ได้สั่ง stop ไว้ด้วยมือ
3. บน Windows เปิด PowerShell สำหรับ tunnel:

```powershell
ssh -N -L 127.0.0.1:3001:127.0.0.1:3000 ai-dev-for-devtomoon@100.121.89.98
```

4. เปิด http://127.0.0.1:3001 และเลือก AItoB Assistant เก็บหน้าต่าง tunnel ไว้

ล็อกหน้าจอ Mac ต่างจาก logout: LaunchAgents นี้ผูกกับ session ผู้ใช้ ไม่ใช่ระบบให้บริการก่อนล็อกอิน การปิดฝา/sleep อาจทำให้เข้าถึงไม่ได้ และถ้า FileVault ต้องปลดล็อกหลังเปิดเครื่อง ต้องทำขั้นนั้นก่อน remote ใช้งาน

SSH สำหรับจัดการ Mac ให้เปิดอีกหน้าต่าง:

```powershell
ssh ai-dev-for-devtomoon@100.121.89.98
```

## 3. ตรวจสถานะบน Mac

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
curl --max-time 10 -sS http://127.0.0.1:11434/api/tags
curl --max-time 10 -sS http://127.0.0.1:8000/health
curl --max-time 10 -sS http://127.0.0.1:8002/health
```

ควรเห็น container สามตัว, gemma4:12b, gateway status ok, assistant status ok การตอบ health ไม่ได้ยืนยันว่า Gmail OAuth และการเรียก tool ยังทำงาน ต้องตรวจงานจริงด้วย

```bash
launchctl print "gui/$(id -u)/com.aitob.lab.ollama"
launchctl print "gui/$(id -u)/com.aitob.lab.gateway"
```

ดู state, pid และ last exit code; ไม่จำเป็นต้องส่งผลทั้งหมดหรือ environment ให้ผู้อื่น

## 4. รีสตาร์ตเฉพาะส่วน

Ollama หรือ Gateway ซึ่งโหลด LaunchAgent อยู่แล้ว:

```bash
launchctl kickstart -k "gui/$(id -u)/com.aitob.lab.ollama"
launchctl kickstart -k "gui/$(id -u)/com.aitob.lab.gateway"
```

รันเฉพาะบรรทัดของบริการที่ต้องการ คำสั่งนี้จะตัดคำขอที่กำลังทำงานอยู่

Gmail หรือ Assistant:

```bash
cd ~/aitob-lab/services
docker compose -f compose.json restart gmail
docker compose -f compose.json restart assistant
```

WebUI:

```bash
cd ~/aitob-lab/open-webui
docker compose restart open-webui
```

ไฟล์ Python ที่ bind mount: restart บริการที่ import ไฟล์นั้นหลังแก้ไข ไม่ต้อง rebuild image หากไม่ได้เปลี่ยน dependencies

## 5. หยุดและเปิดกลับด้วยมือ

หยุด Ollama/Gateway ด้วย bootout เพื่อไม่ให้ KeepAlive เปิดใหม่:

```bash
launchctl bootout "gui/$(id -u)/com.aitob.lab.gateway"
launchctl bootout "gui/$(id -u)/com.aitob.lab.ollama"
```

เปิดกลับ:

```bash
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.aitob.lab.ollama.plist"
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.aitob.lab.gateway.plist"
```

ใช้ bootstrap เมื่อยังไม่โหลดเท่านั้น และตรวจว่าไม่มีตัวเก่าครองพอร์ตอยู่ อย่าเปิด python3 gateway.py หรือ ollama serve ซ้ำขณะที่ LaunchAgent ทำงาน

หยุด container:

```bash
cd ~/aitob-lab/services
docker compose -f compose.json stop
cd ~/aitob-lab/open-webui
docker compose stop open-webui
```

เปิดกลับหลังสั่ง stop:

```bash
cd ~/aitob-lab/services
docker compose -f compose.json up -d
cd ~/aitob-lab/open-webui
docker compose up -d open-webui
```

unless-stopped เคารพการ stop ด้วยมือ อย่าคาดว่าจะกลับมาเองหลัง reboot หากหยุดไว้ ไม่ใช้ down -v เพราะจะกระทบ volume ข้อมูล

## 6. ดู log

```bash
tail -n 60 ~/aitob-lab/logs/com.aitob.lab.ollama.err.log
tail -n 60 ~/aitob-lab/logs/com.aitob.lab.gateway.err.log
cd ~/aitob-lab/services
docker compose -f compose.json logs --tail 60 gmail assistant
cd ~/aitob-lab/open-webui
docker compose logs --tail 60 open-webui
```

ไฟล์ .out.log อยู่ข้าง .err.log ด้วย Container Gmail/Assistant จำกัด log ที่ 3 ไฟล์ × 10 MB ต่อบริการ ส่วน log ของ LaunchAgents ยังไม่ได้ตั้ง rotation ให้ตรวจขนาดเป็นระยะ ตรวจข้อความก่อนแชร์ ไม่ส่ง credentials หรืออีเมลทั้งฉบับโดยไม่จำเป็น

## 7. ชุดทดสอบก่อนเดโม

ใช้แชตใหม่แยกคำถาม บัญชีผู้ใช้ต้องมี User Valves ของตัวเอง

| บัญชี | คำถาม | ผลที่คาดหวัง |
|---|---|---|
| May HR | บริษัทให้วันลาพักร้อนกี่วัน และแจ้งล่วงหน้ากี่วัน | 12 วัน / 3 วัน, hr-leave |
| May HR | ค้นหาอีเมลจาก Canva แล้วอ่านสรุป | ปฏิเสธตามสิทธิ์ |
| May HR | ช่วยทำความสะอาด CSV ค่าใช้จ่าย | ปฏิเสธตามสิทธิ์ |
| Ton Finance | ช่วยทำความสะอาด CSV ค่าใช้จ่าย แล้วสรุปยอดรวม | ใช้ได้ 3 แถว / 2000.00 THB, finance-expenses |
| Ton Finance | ค้นหาอีเมลจาก Canva 1 ฉบับ อ่านแล้วสรุป | มีอ้างอิงและแจ้งเมื่อเนื้อหาถูกตัด |
| Ton Finance | ค้นเอกสารองค์กรเรื่องวันลาพักร้อน | ไม่พบในเอกสารที่มีสิทธิ์อ่าน |

การปฏิเสธเป็นข้อความไม่ใช่หลักฐานเพียงอย่างเดียวของความปลอดภัย: lab มีการทดสอบ code guards ก่อน tool/file/network และ ACL ก่อนเข้า LLM แยกไว้แล้ว

## 8. สำรองข้อมูล

ขณะ WebUI ทำงาน รัน backup_aitob_s2.py ฉบับล่าสุด:

```bash
python3 ~/aitob-lab/backup_aitob_s2.py
```

สำเร็จเมื่อขึ้น PASS ครบ และบอก BACKUP โฟลเดอร์ใต้ ~/aitob-backups/<timestamp> สคริปต์เก็บ consistent SQLite snapshot, โค้ด/config/credentials/data, LaunchAgents ที่ติดตั้งจริง, runtime settings และ SHA256SUMS.txt

ชุดก่อนย้ายบริการที่ตรวจผ่าน: ~/aitob-backups/20261018_091121_456539 ส่วนชุดหลังย้ายให้ใช้ timestamp จากผลรันล่าสุด

สำรองนี้มี API keys และ Gmail token ให้เก็บเป็นความลับ สิทธิ์ folder 700/file 600 เป็นการจำกัดผู้เข้าถึง ไม่ใช่การเข้ารหัส ควรมีสำเนาอีกอุปกรณ์ที่จัดเก็บแบบเข้ารหัส แยกจาก Mac ก่อนใช้กับงานสำคัญ

ขอบเขต: ไม่รวม Docker images, Ollama app/weights, ไฟล์แนบ/vector index หรือ WEBUI_SECRET_KEY ที่อาจเก็บใน WebUI volume; จึงยังไม่ใช่ full-machine backup และยังไม่ได้ทดสอบ restore จริง อย่า prune images ที่ Compose อ้างด้วย sha256 หากยังไม่มีสำเนาหรือวิธี rebuild รุ่นเดิม

## 9. แนวทางกู้คืน

เริ่มจากแยกให้ออกว่า process ล่มหรือข้อมูลเสีย ถ้า process ล่มให้ดู log และเปิดบริการตามข้อ 4–5 ก่อน การ restore จะย้อนบัญชี/แชต/keys กลับตามวันที่สำรอง และไม่ได้แก้ Gmail OAuth ที่ถูกเพิกถอนไปแล้ว

ขั้นตอนกู้คืนข้อมูลที่ต้องทำเมื่อจำเป็น:

1. เลือกชุดที่ PASS ครบ ตรวจ checksum ด้วยคำสั่งด้านล่าง และตรวจว่า image/โมเดลรุ่นเดิมยังอยู่
2. สำรองสภาพปัจจุบันอีกชุดก่อน หยุด WebUI ก่อนเปลี่ยน database; หยุด Gmail/Assistant/Gateway ก่อนเปลี่ยนโค้ดหรือ credentials
3. แตก aitob-lab.tar.gz ลงโฟลเดอร์ staging ที่มีสิทธิ์ส่วนตัวก่อน ไม่ทับ lab เดิมทันที ตรวจไฟล์และเลือกคืนส่วนที่เสีย
4. การคืน webui.db: ใช้ฐานข้อมูล snapshot จากชุดสำรอง เก็บ database ปัจจุบันรวม webui.db-wal และ webui.db-shm ไว้ในโฟลเดอร์ rollback ระหว่างที่ WebUI หยุด แล้วจึงใส่ snapshot อย่าจับคู่ WAL เก่ากับ snapshot ใหม่ เก็บไฟล์อื่นใน volume และ WEBUI_SECRET_KEY เดิมไว้
5. ตรวจ SQLite integrity และใช้สิทธิ์ไฟล์/เจ้าของให้ตรงกับ container ก่อนเปิด WebUI
6. การคืน LaunchAgent: bootout job ก่อน เก็บ plist ปัจจุบันไว้ แล้วคัดลอก com.aitob.lab.*.plist จากชุดสำรองไป ~/Library/LaunchAgents ตรวจ absolute paths และ plutil -lint ก่อน bootstrap
7. เปิดบริการตามข้อ 2/5 และรันทดสอบข้อ 7 ใหม่ รวมการแยกบัญชีและการปฏิเสธสิทธิ์

ตรวจ checksum โดยเปลี่ยน timestamp ให้ตรงชุดที่เลือก:

```bash
cd ~/aitob-backups/<timestamp>
shasum -a 256 -c SHA256SUMS.txt
```

หัวข้อนี้เป็นขั้นตอนสำหรับวางแผน restore ซึ่งยังไม่ได้ทดลอง ไม่ใช่สคริปต์กู้คืนอัตโนมัติ ก่อนคืน database จริงต้องตรวจ volume/mount และยืนยันชุดสำรองที่จะใช้ให้ตรงเครื่อง

## 10. จุดที่ต้องเข้าใจก่อนใช้งานจริง

- สิทธิ์ AItoB ผูกกับผู้ถือ key; ชื่อบัญชี WebUI ไม่ได้บังคับผูกกับ identity ใน Gateway ผู้ถือ key Finance สามารถใช้สิทธิ์ Finance ได้
- UserValves แยกผู้ใช้ แต่ไม่ได้ถือว่าเข้ารหัสที่จัดเก็บโดยอัตโนมัติ อย่าแชร์ฐานข้อมูลหรือ dump settings
- เอกสารยังเป็นตัวอย่าง ค้นแบบคำสำคัญ; CSV เป็น fixed file ไม่ใช่ upload ทั่วไป
- Gmail ใช้บัญชีเจ้าของหนึ่งกล่อง เฉพาะ AItoB-Demo/read-only/ข้อความบางส่วน OAuth อาจต้องอนุญาตใหม่ตามสถานะของ Google project
- ยังไม่ได้ทำ high availability, load test หรือ restore drill
- อย่าเพิ่ม global Finance key หรือยกระดับ May/Ton เป็น admin เพื่อแก้ปัญหาการเข้าถึงโมเดล ให้แก้ model access และใช้ per-user keys ตามเดิม

## 11. ถ้าเปิดหน้าแชตไม่ได้

- localhost:3001 refused บน Windows: ตรวจ SSH tunnel ก่อน; tunnel ต้องเปิดใหม่หลัง Mac reboot/connection หลุด
- Mac:3000 ไม่ตอบ: ตรวจ Docker Desktop และ WebUI container
- /8002/health ตอบ แต่แชตไม่สำเร็จ: ตรวจ Gateway /8000, Ollama /11434, log และ key
- Gmail อย่างเดียวล้มเหลว: ตรวจ container gmail, OAuth/บัญชีเจ้าของ/label โดยไม่ขยายสิทธิ์หรือพิมพ์ token ลงแชต

แหล่งอ้างอิง: https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html และ https://docs.docker.com/desktop/settings-and-maintenance/settings/
