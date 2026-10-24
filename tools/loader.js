// AItoB Enterprise Assistant - Onboarding, Integrations Hub & Quick Actions
(function() {
  console.log("[AItoB] Enterprise Assistant UI Initialized");

  const ONBOARDING_KEY = 'aitob_has_seen_onboarding';
  const N8N_WEBHOOK_KEY = 'aitob_n8n_webhook_url';

  // 1. Insert prompt into Open WebUI chat input
  function insertPromptIntoChat(text) {
    closeGetStartedModal();
    setTimeout(() => {
      const el = document.querySelector('#chat-textarea') || 
                 document.querySelector('textarea#chat-input') || 
                 document.querySelector('textarea') || 
                 document.querySelector('[contenteditable="true"]');
      if (el) {
        if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
          el.value = text;
          el.style.height = 'auto';
          el.style.height = Math.min(el.scrollHeight, 200) + 'px';
          el.dispatchEvent(new Event('input', { bubbles: true }));
          el.dispatchEvent(new Event('change', { bubbles: true }));
        } else {
          el.innerText = text;
          el.dispatchEvent(new Event('input', { bubbles: true }));
        }
        el.focus();
      }
    }, 150);
  }

  // 2. n8n Webhook configuration
  function promptN8nWebhook() {
    let current = '';
    try { current = localStorage.getItem(N8N_WEBHOOK_KEY) || ''; } catch(e) {}
    const url = prompt('ระบุ n8n Webhook URL สำหรับเชื่อมต่อระบบอัตโนมัติ:\n(เช่น http://n8n.local:5678/webhook/aitob-sync)', current);
    if (url !== null) {
      if (url.trim()) {
        try { localStorage.setItem(N8N_WEBHOOK_KEY, url.trim()); } catch(e) {}
        alert('🟢 บันทึก n8n Webhook URL เรียบร้อยแล้ว:\n' + url.trim());
      } else {
        try { localStorage.removeItem(N8N_WEBHOOK_KEY); } catch(e) {}
        alert('ล้างการตั้งค่า n8n Webhook เรียบร้อยแล้ว');
      }
      refreshIntegrationsStatus();
    }
  }

  function testN8nWebhook() {
    let url = '';
    try { url = localStorage.getItem(N8N_WEBHOOK_KEY); } catch(e) {}
    if (!url) {
      promptN8nWebhook();
      return;
    }
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event: 'ping', test: true, source: 'AItoB Integrations Hub', timestamp: Date.now() })
    }).then(res => {
      alert(`🟢 ยิงทดสอบ Webhook สำเร็จ (Status: ${res.status})`);
    }).catch(err => {
      alert(`⚠️ การเชื่อมต่อ Webhook ล้มเหลว:\n${err.message}\n(ตรวจสอบว่า n8n กำลังทำงานและเปิดรับ Webhook หรือไม่)`);
    });
  }

  function refreshIntegrationsStatus() {
    const n8nStatusEl = document.getElementById('aitob-integ-n8n-status');
    const n8nDescEl = document.getElementById('aitob-integ-n8n-desc');
    let savedUrl = '';
    try { savedUrl = localStorage.getItem(N8N_WEBHOOK_KEY) || ''; } catch(e) {}
    if (n8nStatusEl) {
      if (savedUrl) {
        n8nStatusEl.className = 'aitob-integ-status active';
        n8nStatusEl.innerHTML = '🟢 เชื่อมต่อแล้ว';
      } else {
        n8nStatusEl.className = 'aitob-integ-status setup';
        n8nStatusEl.innerHTML = '⚡ พร้อมเชื่อมต่อ';
      }
    }
    if (n8nDescEl) {
      if (savedUrl) {
        n8nDescEl.innerText = `Webhook ที่บันทึกไว้: ${savedUrl.length > 40 ? savedUrl.substring(0, 37) + '...' : savedUrl}`;
      } else {
        n8nDescEl.innerText = 'เชื่อมต่อ Webhook ไปยัง n8n เพื่อรัน Flow อัตโนมัติ เช่น แจ้งเตือน Slack, บันทึกลง ERP หรือ sync ข้อมูล';
      }
    }
  }

  // 3. Tab switching
  function switchOnboardingTab(tabKey) {
    const modal = document.getElementById('aitob-onboarding-modal');
    if (!modal) return;
    const tabs = modal.querySelectorAll('.aitob-onboarding-tab');
    tabs.forEach(tab => {
      if (tab.getAttribute('data-tab') === tabKey) tab.classList.add('active');
      else tab.classList.remove('active');
    });

    const panels = modal.querySelectorAll('.aitob-tab-panel');
    panels.forEach(panel => {
      if (panel.getAttribute('data-panel') === tabKey) panel.classList.add('active');
      else panel.classList.remove('active');
    });

    if (tabKey === 'integrations') {
      refreshIntegrationsStatus();
    }
  }

  // 4. Modal DOM construction
  function getOrCreateGetStartedModal() {
    let overlay = document.getElementById('aitob-onboarding-overlay');
    if (overlay) return overlay;

    overlay = document.createElement('div');
    overlay.id = 'aitob-onboarding-overlay';
    overlay.className = 'aitob-onboarding-overlay';
    overlay.onclick = (e) => {
      if (e.target === overlay) closeGetStartedModal();
    };

    const modal = document.createElement('div');
    modal.id = 'aitob-onboarding-modal';
    modal.className = 'aitob-onboarding-modal';
    modal.innerHTML = `
      <!-- Header -->
      <div class="aitob-onboarding-header">
        <div class="aitob-onboarding-title-group">
          <div class="aitob-onboarding-title-row">
            <div class="aitob-onboarding-title">
              <span>🚀</span> ยินดีต้อนรับสู่ AItoB
            </div>
            <span class="aitob-onboarding-badge">Enterprise Local AI</span>
          </div>
          <div class="aitob-onboarding-subtitle">
            ศูนย์รวมคู่มือเริ่มต้นใช้งาน ตัวอย่างคำสั่ง และการเชื่อมต่อระบบทั้งหมดขององค์กร
          </div>
        </div>
        <button class="aitob-onboarding-close" id="aitob-modal-close-icon" title="ปิด">✕</button>
      </div>

      <!-- Navigation Tabs (4 Tabs) -->
      <div class="aitob-onboarding-tabs">
        <button type="button" class="aitob-onboarding-tab active" data-tab="overview">
          <span>🛡️</span> ภาพรวม & ความปลอดภัย
        </button>
        <button type="button" class="aitob-onboarding-tab" data-tab="integrations">
          <span>🔗</span> เชื่อมต่อระบบ (Integrations)
        </button>
        <button type="button" class="aitob-onboarding-tab" data-tab="finance">
          <span>💰</span> ตรวจสอบค่าใช้จ่าย
        </button>
        <button type="button" class="aitob-onboarding-tab" data-tab="docs">
          <span>📄</span> ค้นหาเอกสาร & อีเมล
        </button>
      </div>

      <!-- Body / Tab Panels -->
      <div class="aitob-onboarding-body">
        
        <!-- Tab 1: Overview & Security -->
        <div class="aitob-tab-panel active" data-panel="overview">
          <div class="aitob-info-banner">
            <span class="aitob-info-banner-icon">🛡️</span>
            <div class="aitob-info-banner-content">
              <strong>มาตรฐานความปลอดภัยระดับองค์กร (Data Sovereignty):</strong><br>
              AItoB ประมวลผลเอกสาร อีเมล และข้อมูลลับอยู่บนเครื่องแม่ข่ายภายในองค์กร 100% ไม่มีข้อมูลรั่วไหลสู่ Cloud ภายนอก พร้อมระบบตรวจสอบสิทธิ์ระดับโฟลเดอร์และคีย์ประจำแผนก
            </div>
          </div>

          <div class="aitob-feature-cards">
            <div class="aitob-feature-mini-card">
              <div class="aitob-feature-mini-card-title"><span>🔒</span> แยกสิทธิ์ตามแผนก</div>
              <div class="aitob-feature-mini-card-desc">กักเก็บข้อมูลการเงินและบุคคลแยกกันอย่างเด็ดขาด ผ่าน Gateway Auth Key</div>
            </div>
            <div class="aitob-feature-mini-card">
              <div class="aitob-feature-mini-card-title"><span>⚡</span> Multi-Model Ready</div>
              <div class="aitob-feature-mini-card-desc">สลับการทำงานระหว่าง Local Ollama (Gemma4:12b) หรือ External Claude/OpenAI ได้</div>
            </div>
            <div class="aitob-feature-mini-card">
              <div class="aitob-feature-mini-card-title"><span>📑</span> Evidence & Audit</div>
              <div class="aitob-feature-mini-card-desc">คำตอบทุกชิ้นจาก AI มีการระบุเอกสารอ้างอิงและบันทึกประวัติเพื่อความโปร่งใส</div>
            </div>
          </div>

          <div class="aitob-prompts-container">
            <div class="aitob-prompts-title">💡 วิธีเริ่มต้นใช้งานด่วน:</div>
            <div class="aitob-prompt-chip" data-prompt="ช่วยแนะนำหน่อยว่าระบบ AItoB ทำอะไรได้บ้าง และมีเครื่องมืออะไรให้ใช้งาน">
              <span class="aitob-prompt-chip-text">"ช่วยแนะนำหน่อยว่าระบบ AItoB ทำอะไรได้บ้าง และมีเครื่องมืออะไรให้ใช้งาน"</span>
              <span class="aitob-prompt-chip-badge">ลองใช้คำสั่งนี้ ↵</span>
            </div>
            <div class="aitob-prompt-chip" data-prompt="ตรวจสอบสถานะการเชื่อมต่อ Gateway และสิทธิ์เข้าถึงเครื่องมือของฉัน">
              <span class="aitob-prompt-chip-text">"ตรวจสอบสถานะการเชื่อมต่อ Gateway และสิทธิ์เข้าถึงเครื่องมือของฉัน"</span>
              <span class="aitob-prompt-chip-badge">ลองใช้คำสั่งนี้ ↵</span>
            </div>
          </div>
        </div>

        <!-- Tab 2: Integrations Hub -->
        <div class="aitob-tab-panel" data-panel="integrations">
          <div class="aitob-info-banner">
            <span class="aitob-info-banner-icon">🔗</span>
            <div class="aitob-info-banner-content">
              <strong>ศูนย์รวมการเชื่อมต่อระบบ (Integrations Hub):</strong><br>
              ตรวจสอบและตั้งค่าการเชื่อมต่อระหว่าง AItoB กับระบบภายนอก เพื่อให้ผู้ช่วย AI มีข้อมูลสนับสนุนการทำงานอย่างเต็มประสิทธิภาพ
            </div>
          </div>

          <div class="aitob-integrations-grid">
            <!-- 1. Database & Documents -->
            <div class="aitob-integration-card">
              <div>
                <div class="aitob-integ-header">
                  <div class="aitob-integ-name-group">
                    <div class="aitob-integ-icon">🗄️</div>
                    <div>
                      <div class="aitob-integ-name">Database & Documents</div>
                      <div class="aitob-integ-category">คลังข้อมูลและเอกสารองค์กร</div>
                    </div>
                  </div>
                  <span class="aitob-integ-status active">🟢 พร้อมใช้งาน RAG</span>
                </div>
                <div class="aitob-integ-desc">
                  เชื่อมต่อไฟล์นโยบายบริษัท ระเบียบสวัสดิการ และไฟล์ CSV ค่าใช้จ่ายภายในองค์กร เพื่อค้นหาแบบ Vector Search
                </div>
              </div>
              <div class="aitob-integ-footer">
                <span style="font-size: 11px; color: #64748b;">4 หมวดเอกสารพร้อมค้น</span>
                <button type="button" class="aitob-integ-btn secondary" id="aitob-integ-db-btn">
                  🔍 ลองค้นหาข้อมูล
                </button>
              </div>
            </div>

            <!-- 2. n8n Automation -->
            <div class="aitob-integration-card">
              <div>
                <div class="aitob-integ-header">
                  <div class="aitob-integ-name-group">
                    <div class="aitob-integ-icon">⚡</div>
                    <div>
                      <div class="aitob-integ-name">n8n Workflow Automation</div>
                      <div class="aitob-integ-category">ระบบส่งต่องานอัตโนมัติ</div>
                    </div>
                  </div>
                  <span class="aitob-integ-status setup" id="aitob-integ-n8n-status">⚡ พร้อมเชื่อมต่อ</span>
                </div>
                <div class="aitob-integ-desc" id="aitob-integ-n8n-desc">
                  เชื่อมต่อ Webhook ไปยัง n8n เพื่อรัน Flow อัตโนมัติ เช่น แจ้งเตือน Slack, บันทึกลง ERP หรือ sync ข้อมูล
                </div>
              </div>
              <div class="aitob-integ-footer">
                <button type="button" class="aitob-integ-btn secondary" id="aitob-integ-n8n-test-btn">
                  🔔 Test Ping
                </button>
                <button type="button" class="aitob-integ-btn primary" id="aitob-integ-n8n-config-btn">
                  ⚙️ ตั้งค่า Webhook
                </button>
              </div>
            </div>

            <!-- 3. Gmail Service -->
            <div class="aitob-integration-card">
              <div>
                <div class="aitob-integ-header">
                  <div class="aitob-integ-name-group">
                    <div class="aitob-integ-icon">📧</div>
                    <div>
                      <div class="aitob-integ-name">Gmail & Workspace</div>
                      <div class="aitob-integ-category">ระบบอีเมลองค์กร</div>
                    </div>
                  </div>
                  <span class="aitob-integ-status ready">🟢 พอร์ต 8001 Ready</span>
                </div>
                <div class="aitob-integ-desc">
                  เชื่อมต่อการค้นหาและสรุปเนื้อหาอีเมลตามขอบเขตความปลอดภัยของฝ่าย ช่วยสรุปการประชุมและเอกสารแนบสำคัญ
                </div>
              </div>
              <div class="aitob-integ-footer">
                <span style="font-size: 11px; color: #60a5fa;">● OAuth Safe Scope</span>
                <button type="button" class="aitob-integ-btn secondary" id="aitob-integ-gmail-test-btn">
                  📨 ลองค้นหาอีเมล
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Tab 3: Finance Expense Audit -->
        <div class="aitob-tab-panel" data-panel="finance">
          <div class="aitob-info-banner">
            <span class="aitob-info-banner-icon">💰</span>
            <div class="aitob-info-banner-content">
              <strong>ผู้ช่วยตรวจสอบค่าใช้จ่าย (Finance Expense Audit):</strong><br>
              ตรวจสอบความถูกต้องของไฟล์ CSV และใบเสร็จเบิกจ่าย เปรียบเทียบกับกฎระเบียบของบริษัท ตรวจจับรายการเบิกซ้ำ ยอดเงินเกินเกณฑ์ และสรุปยอดที่อนุมัติได้แบบอัตโนมัติ
            </div>
          </div>

          <div class="aitob-prompts-container">
            <div class="aitob-prompts-title">💡 ตัวอย่างคำสั่งที่คลิกทดลองได้ทันที:</div>
            <div class="aitob-prompt-chip" data-prompt="ช่วยตรวจสอบไฟล์ค่าใช้จ่ายล่าสุดให้หน่อยว่ามีรายการไหนผิดระเบียบบริษัทหรือผิดปกติไหม">
              <span class="aitob-prompt-chip-text">"ช่วยตรวจสอบไฟล์ค่าใช้จ่ายล่าสุดให้หน่อยว่ามีรายการไหนผิดระเบียบบริษัทหรือผิดปกติไหม"</span>
              <span class="aitob-prompt-chip-badge">ลองใช้คำสั่งนี้ ↵</span>
            </div>
            <div class="aitob-prompt-chip" data-prompt="สรุปยอดการเบิกจ่ายค่าใช้จ่ายทั้งหมดแยกตามแผนก พร้อมแสดงรายการที่ผ่านและถูกปฏิเสธ">
              <span class="aitob-prompt-chip-text">"สรุปยอดการเบิกจ่ายค่าใช้จ่ายทั้งหมดแยกตามแผนก พร้อมแสดงรายการที่ผ่านและถูกปฏิเสธ"</span>
              <span class="aitob-prompt-chip-badge">ลองใช้คำสั่งนี้ ↵</span>
            </div>
            <div class="aitob-prompt-chip" data-prompt="มีรายการเบิกจ่ายค่าเดินทางหรือค่าอาหารใดที่ซ้ำซ้อนกันในสัปดาห์นี้หรือไม่">
              <span class="aitob-prompt-chip-text">"มีรายการเบิกจ่ายค่าเดินทางหรือค่าอาหารใดที่ซ้ำซ้อนกันในสัปดาห์นี้หรือไม่"</span>
              <span class="aitob-prompt-chip-badge">ลองใช้คำสั่งนี้ ↵</span>
            </div>
          </div>
        </div>

        <!-- Tab 4: Docs & Gmail RAG -->
        <div class="aitob-tab-panel" data-panel="docs">
          <div class="aitob-info-banner">
            <span class="aitob-info-banner-icon">📄</span>
            <div class="aitob-info-banner-content">
              <strong>ผู้ช่วยค้นหาเอกสาร & อีเมล (Enterprise RAG):</strong><br>
              ค้นหานโยบายภายในบริษัทและอีเมลสำคัญได้อย่างรวดเร็ว โดยคำตอบทุกครั้งจะแสดง <em>"แหล่งข้อมูลที่ระบบใช้"</em> พร้อมรหัสอ้างอิง เพื่อให้คุณตรวจสอบความถูกต้องได้เสมอ
            </div>
          </div>

          <div class="aitob-prompts-container">
            <div class="aitob-prompts-title">💡 ตัวอย่างคำสั่งที่คลิกทดลองได้ทันที:</div>
            <div class="aitob-prompt-chip" data-prompt="ค้นหาและสรุปนโยบายการเบิกค่าเดินทางและค่าเบี้ยเลี้ยงของบริษัทให้หน่อย">
              <span class="aitob-prompt-chip-text">"ค้นหาและสรุปนโยบายการเบิกค่าเดินทางและค่าเบี้ยเลี้ยงของบริษัทให้หน่อย"</span>
              <span class="aitob-prompt-chip-badge">ลองใช้คำสั่งนี้ ↵</span>
            </div>
            <div class="aitob-prompt-chip" data-prompt="สรุปอีเมลสำคัญที่มีเรื่องการอนุมัติงบประมาณและโปรเจกต์ใหม่ให้หน่อย">
              <span class="aitob-prompt-chip-text">"สรุปอีเมลสำคัญที่มีเรื่องการอนุมัติงบประมาณและโปรเจกต์ใหม่ให้หน่อย"</span>
              <span class="aitob-prompt-chip-badge">ลองใช้คำสั่งนี้ ↵</span>
            </div>
            <div class="aitob-prompt-chip" data-prompt="ช่วยตรวจสอบระเบียบการลาพักร้อน สิทธิประโยชน์ และวันหยุดพิเศษของพนักงาน">
              <span class="aitob-prompt-chip-text">"ช่วยตรวจสอบระเบียบการลาพักร้อน สิทธิประโยชน์ และวันหยุดพิเศษของพนักงาน"</span>
              <span class="aitob-prompt-chip-badge">ลองใช้คำสั่งนี้ ↵</span>
            </div>
          </div>
        </div>

      </div>

      <!-- Footer -->
      <div class="aitob-onboarding-footer">
        <label class="aitob-checkbox-label">
          <input type="checkbox" id="aitob-dont-show-again">
          <span>ไม่ต้องแสดงหน้าต่างนี้อัตโนมัติเมื่อเริ่มต้น</span>
        </label>
        <div class="aitob-footer-actions">
          <button type="button" class="aitob-btn-dismiss" id="aitob-modal-dismiss-btn">ปิด</button>
          <button type="button" class="aitob-btn-primary-action" id="aitob-modal-confirm-btn">
            เข้าใจแล้ว เริ่มต้นใช้งาน 🚀
          </button>
        </div>
      </div>
    `;

    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    // Bind event listeners
    modal.querySelector('#aitob-modal-close-icon').onclick = () => closeGetStartedModal();
    modal.querySelector('#aitob-modal-dismiss-btn').onclick = () => closeGetStartedModal();
    modal.querySelector('#aitob-modal-confirm-btn').onclick = () => {
      try { localStorage.setItem(ONBOARDING_KEY, 'true'); } catch(e) {}
      closeGetStartedModal();
    };

    modal.querySelectorAll('.aitob-onboarding-tab').forEach(tab => {
      tab.onclick = () => switchOnboardingTab(tab.getAttribute('data-tab'));
    });

    modal.querySelectorAll('.aitob-prompt-chip').forEach(chip => {
      chip.onclick = () => {
        const promptText = chip.getAttribute('data-prompt');
        if (promptText) insertPromptIntoChat(promptText);
      };
    });

    modal.querySelector('#aitob-integ-db-btn').onclick = () => {
      switchOnboardingTab('docs');
    };
    modal.querySelector('#aitob-integ-n8n-config-btn').onclick = () => {
      promptN8nWebhook();
    };
    modal.querySelector('#aitob-integ-n8n-test-btn').onclick = () => {
      testN8nWebhook();
    };
    modal.querySelector('#aitob-integ-gmail-test-btn').onclick = () => {
      switchOnboardingTab('docs');
    };

    return overlay;
  }

  function openGetStartedModal(defaultTab = 'overview') {
    getOrCreateGetStartedModal();
    switchOnboardingTab(defaultTab);
    const overlay = document.getElementById('aitob-onboarding-overlay');
    if (overlay) overlay.classList.add('active');
  }

  function closeGetStartedModal() {
    const overlay = document.getElementById('aitob-onboarding-overlay');
    if (overlay) overlay.classList.remove('active');
    const checkbox = document.getElementById('aitob-dont-show-again');
    if (checkbox && checkbox.checked) {
      try { localStorage.setItem(ONBOARDING_KEY, 'true'); } catch(e) {}
    }
  }

  // 5. Sidebar & Header Trigger Buttons
  function updateSidebarGetStarted() {
    let btn = document.getElementById('nav-get-started-btn');
    if (!btn) {
      const target = document.querySelector('a#sidebar-new-chat-button') || document.querySelector('#sidebar-chats');
      if (target && target.parentElement) {
        btn = document.createElement('div');
        btn.id = 'nav-get-started-btn';
        btn.innerHTML = `
          <div style="display: flex; align-items: center; justify-content: center; width: 22px; height: 22px;">
            <span style="font-size: 16px;">🚀</span>
          </div>
          <span style="font-weight: 600; font-size: 13.5px; color: #60a5fa; flex: 1;">เริ่มต้นใช้งาน</span>
          <span style="background: rgba(59, 130, 246, 0.2); color: #93c5fd; font-size: 10px; font-weight: bold; padding: 1px 6px; border-radius: 6px; border: 1px solid rgba(59, 130, 246, 0.3);">Guide</span>
        `;
        btn.onclick = () => openGetStartedModal('overview');
        if (target.nextSibling) target.parentElement.insertBefore(btn, target.nextSibling);
        else target.parentElement.appendChild(btn);
      }
    }
  }

  function updateHeaderGetStarted() {
    const headerEl = document.querySelector('header');
    if (!headerEl || document.getElementById('aitob-header-btn-getstarted')) return;
    const titleContainer = headerEl.querySelector('.line-clamp-1, [class*="title"]') || headerEl.children[0];
    if (titleContainer) {
      const btn = document.createElement('button');
      btn.id = 'aitob-header-btn-getstarted';
      btn.className = 'aitob-header-btn-getstarted';
      btn.innerHTML = `🚀 เริ่มต้นใช้งาน`;
      btn.title = 'เปิดคู่มือเริ่มต้นใช้งานและการเชื่อมต่อระบบ (Get Started)';
      btn.onclick = () => openGetStartedModal('overview');
      titleContainer.appendChild(btn);
    }
  }

  function checkFirstTimeUser() {
    try {
      const hasSeen = localStorage.getItem(ONBOARDING_KEY);
      if (!hasSeen) {
        setTimeout(() => {
          openGetStartedModal('overview');
        }, 1200);
      }
    } catch(e) {}
  }

  // Throttled lifecycle loop (every 1.5s)
  setInterval(() => {
    updateSidebarGetStarted();
    updateHeaderGetStarted();
  }, 1500);

  // Init
  setTimeout(() => {
    getOrCreateGetStartedModal();
    updateSidebarGetStarted();
    updateHeaderGetStarted();
    checkFirstTimeUser();
  }, 800);
})();
