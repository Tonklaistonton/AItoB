// AItoB Enterprise Assistant - Connect Services & Onboarding Hub
// Inspired by executive enterprise onboarding workflow
(function() {
  console.log("[AItoB] Enterprise Connect Services Wizard Initialized");

  const ONBOARDING_KEY = 'aitob_has_seen_onboarding_v2';
  const INTEG_CONFIG_KEY = 'aitob_integrations_config';
  const DB_CONFIG_KEY = 'aitob_db_connection_url';
  const N8N_WEBHOOK_KEY = 'aitob_n8n_webhook_url';
  const LINE_TOKEN_KEY = 'aitob_line_access_token';
  const GMAIL_CONFIG_KEY = 'aitob_gmail_app_password';

  // 1. Toast Notification Helper
  function showToast(message) {
    let toast = document.getElementById('aitob-toast-notification');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'aitob-toast-notification';
      toast.className = 'aitob-toast-notification';
      document.body.appendChild(toast);
    }
    toast.innerHTML = message;
    toast.classList.add('show');
    setTimeout(() => {
      toast.classList.remove('show');
    }, 4000);
  }

  // 2. Preferences Storage
  function getIntegConfig() {
    try {
      const raw = localStorage.getItem(INTEG_CONFIG_KEY);
      if (raw) return JSON.parse(raw);
    } catch(e) {}
    return { db: false, n8n: false, line: false, gmail: false };
  }

  function saveIntegConfig(cfg) {
    try {
      localStorage.setItem(INTEG_CONFIG_KEY, JSON.stringify(cfg));
    } catch(e) {}
  }

  // 3. Insert Prompt into Open WebUI chat input
  function insertPromptIntoChat(text) {
    closeConnectServicesModal();
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

  // 4. Test n8n Webhook
  function testN8nWebhook(url) {
    const targetUrl = (url || '').trim();
    if (!targetUrl) {
      alert('กรุณากรอก n8n Webhook URL ก่อนกดทดสอบครับ');
      const input = document.getElementById('input-service-n8n');
      if (input) input.focus();
      return;
    }

    fetch(targetUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        event: 'ping',
        test: true,
        source: 'AItoB Connect Services',
        timestamp: Date.now()
      })
    }).then(res => {
      showToast(`🟢 เชื่อมต่อ n8n สำเร็จ! (Response Status: ${res.status})`);
      try { localStorage.setItem(N8N_WEBHOOK_KEY, targetUrl); } catch(e) {}
    }).catch(err => {
      alert(`⚠️ การเชื่อมต่อ Webhook ล้มเหลว:\n${err.message}\n(ตรวจสอบว่า n8n กำลังทำงานและเปิดรับ Webhook หรือไม่)`);
    });
  }

  // 5. Toggle Service Card and Drawer
  function toggleService(serviceId, forceState) {
    const card = document.getElementById(`card-service-${serviceId}`);
    const chk = document.getElementById(`chk-service-${serviceId}`);
    if (!card || !chk) return;

    const newState = (forceState !== undefined) ? forceState : !chk.checked;
    chk.checked = newState;
    if (newState) {
      card.classList.add('checked');
      const input = card.querySelector('.aitob-field-input');
      if (input) setTimeout(() => input.focus(), 120);
    } else {
      card.classList.remove('checked');
    }
  }

  // 6. Modal Construction & Event Binding
  function getOrCreateConnectModal() {
    let overlay = document.getElementById('aitob-onboarding-overlay');
    if (overlay) return overlay;

    overlay = document.createElement('div');
    overlay.id = 'aitob-onboarding-overlay';
    overlay.className = 'aitob-onboarding-overlay';
    overlay.onclick = (e) => {
      if (e.target === overlay) closeConnectServicesModal();
    };

    const cfg = getIntegConfig();
    const savedDb = localStorage.getItem(DB_CONFIG_KEY) || '';
    const savedN8n = localStorage.getItem(N8N_WEBHOOK_KEY) || '';
    const savedLine = localStorage.getItem(LINE_TOKEN_KEY) || '';
    const savedGmail = localStorage.getItem(GMAIL_CONFIG_KEY) || '';

    const modal = document.createElement('div');
    modal.id = 'aitob-onboarding-modal';
    modal.className = 'aitob-modal-card';
    modal.innerHTML = `
      <!-- Header -->
      <div class="aitob-modal-header">
        <div class="aitob-modal-title-wrap">
          <div class="aitob-modal-title-row">
            <h2 class="aitob-modal-title">เชื่อมต่อบริการที่คุณต้องการ</h2>
            <span class="aitob-modal-badge">Setup Hub</span>
          </div>
          <p class="aitob-modal-subtitle">Connect และตั้งค่าช่องทางเชื่อมต่อเพื่อเริ่มต้นใช้งาน</p>
        </div>
        <button type="button" class="aitob-modal-close-btn" id="aitob-modal-close-icon" title="ปิด">✕</button>
      </div>

      <!-- 2x2 Services Grid -->
      <div class="aitob-services-grid">
        <!-- 1. Database -->
        <div class="aitob-service-card ${cfg.db ? 'checked' : ''}" id="card-service-db">
          <div class="aitob-service-card-top" id="top-service-db">
            <div class="aitob-service-info">
              <div class="aitob-service-icon db-icon">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
                  <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path>
                  <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>
                </svg>
              </div>
              <span class="aitob-service-name">Database</span>
            </div>
            <input type="checkbox" id="chk-service-db" class="aitob-service-chk" ${cfg.db ? 'checked' : ''}>
          </div>
          <div class="aitob-service-drawer" id="drawer-service-db">
            <label class="aitob-field-label">กรอก URL และรหัสผ่าน Database</label>
            <input type="text" id="input-service-db" class="aitob-field-input" placeholder="กรอก URL และรหัสผ่าน Database (เช่น postgresql://...)" value="${savedDb}">
          </div>
        </div>

        <!-- 2. n8n -->
        <div class="aitob-service-card ${cfg.n8n ? 'checked' : ''}" id="card-service-n8n">
          <div class="aitob-service-card-top" id="top-service-n8n">
            <div class="aitob-service-info">
              <div class="aitob-service-icon n8n-icon">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#ea580c" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="6" cy="12" r="3"></circle>
                  <circle cx="18" cy="6" r="3"></circle>
                  <circle cx="18" cy="18" r="3"></circle>
                  <path d="M9 12h6"></path>
                  <path d="M9 12l6-6"></path>
                  <path d="M9 12l6 6"></path>
                </svg>
              </div>
              <span class="aitob-service-name">n8n</span>
            </div>
            <input type="checkbox" id="chk-service-n8n" class="aitob-service-chk" ${cfg.n8n ? 'checked' : ''}>
          </div>
          <div class="aitob-service-drawer" id="drawer-service-n8n">
            <label class="aitob-field-label">n8n Webhook URL</label>
            <div class="aitob-input-with-btn">
              <input type="text" id="input-service-n8n" class="aitob-field-input" placeholder="http://localhost:5678/webhook/..." value="${savedN8n}">
              <button type="button" class="aitob-test-ping-btn" id="btn-test-n8n" title="ทดสอบเชื่อมต่อ">🔔 Test Ping</button>
            </div>
          </div>
        </div>

        <!-- 3. LINE -->
        <div class="aitob-service-card ${cfg.line ? 'checked' : ''}" id="card-service-line">
          <div class="aitob-service-card-top" id="top-service-line">
            <div class="aitob-service-info">
              <div class="aitob-service-icon line-icon">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="#06C755">
                  <path d="M12 2C6.48 2 2 5.82 2 10.53c0 2.97 1.8 5.6 4.6 7.08l-.7 2.6c-.1.38.3.7.63.5l3.52-2.1c.63.13 1.28.2 1.95.2 5.52 0 10-3.82 10-8.53S17.52 2 12 2z"/>
                </svg>
              </div>
              <span class="aitob-service-name">LINE</span>
            </div>
            <input type="checkbox" id="chk-service-line" class="aitob-service-chk" ${cfg.line ? 'checked' : ''}>
          </div>
          <div class="aitob-service-drawer" id="drawer-service-line">
            <label class="aitob-field-label">LINE Channel Access Token</label>
            <input type="text" id="input-service-line" class="aitob-field-input" placeholder="กรอก Channel Access Token (หรือเว้นว่างเพื่อใช้พอร์ต 8003)" value="${savedLine}">
          </div>
        </div>

        <!-- 4. Gmail -->
        <div class="aitob-service-card ${cfg.gmail ? 'checked' : ''}" id="card-service-gmail">
          <div class="aitob-service-card-top" id="top-service-gmail">
            <div class="aitob-service-info">
              <div class="aitob-service-icon gmail-icon">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                  <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" stroke="#EA4335" stroke-width="2"/>
                  <path d="M22 6l-10 7L2 6" stroke="#EA4335" stroke-width="2"/>
                </svg>
              </div>
              <span class="aitob-service-name">Gmail</span>
            </div>
            <input type="checkbox" id="chk-service-gmail" class="aitob-service-chk" ${cfg.gmail ? 'checked' : ''}>
          </div>
          <div class="aitob-service-drawer" id="drawer-service-gmail">
            <label class="aitob-field-label">Gmail App Password</label>
            <div class="aitob-password-wrap">
              <input type="password" id="input-service-gmail" class="aitob-field-input" placeholder="•••• •••• •••• ••••" value="${savedGmail}">
              <button type="button" class="aitob-pwd-toggle" id="btn-toggle-gmail-pwd" title="แสดง/ซ่อนรหัสผ่าน">👁️</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Quick Prompts Accordion (Optional Explorations) -->
      <div class="aitob-quick-prompts-toggle" id="aitob-quick-prompts-toggle">
        <span>💡 ดูตัวอย่างคำสั่งยอดนิยม (Finance & Docs RAG)</span>
        <span class="aitob-arrow" id="aitob-prompts-arrow">▾</span>
      </div>
      <div class="aitob-quick-prompts-drawer" id="aitob-quick-prompts-drawer">
        <div class="aitob-prompt-chip-list">
          <div class="aitob-chip" data-prompt="ช่วยตรวจสอบไฟล์ค่าใช้จ่ายล่าสุดให้หน่อยว่ามีรายการไหนผิดระเบียบบริษัทหรือผิดปกติไหม">
            💰 ตรวจสอบไฟล์ค่าใช้จ่ายล่าสุด
          </div>
          <div class="aitob-chip" data-prompt="ค้นหาและสรุปนโยบายการเบิกค่าเดินทางและค่าเบี้ยเลี้ยงของบริษัทให้หน่อย">
            📄 สรุปนโยบายการเบิกค่าเดินทาง
          </div>
          <div class="aitob-chip" data-prompt="สรุปอีเมลสำคัญที่มีเรื่องการอนุมัติงบประมาณและโปรเจกต์ใหม่ให้หน่อย">
            📧 สรุปอีเมลสำคัญ & งบประมาณ
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="aitob-modal-footer">
        <div class="aitob-footer-subrow">
          <label class="aitob-skip-label">
            <input type="checkbox" id="chk-skip-or-later">
            <span>ข้ามการตั้งค่านี้ไปก่อน <a href="javascript:void(0)" id="link-setup-later">(ตั้งค่าภายหลังได้)</a></span>
          </label>
        </div>
        <button type="button" class="aitob-btn-save-continue" id="btn-save-continue">
          บันทึกและดำเนินการต่อ
        </button>
      </div>
    `;

    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    // Bind Close Events
    modal.querySelector('#aitob-modal-close-icon').onclick = () => closeConnectServicesModal();

    // Bind Service Card Clicks
    const services = ['db', 'n8n', 'line', 'gmail'];
    services.forEach(s => {
      const top = modal.querySelector(`#top-service-${s}`);
      const chk = modal.querySelector(`#chk-service-${s}`);
      if (top) {
        top.onclick = (e) => {
          if (e.target !== chk) {
            toggleService(s);
          }
        };
      }
      if (chk) {
        chk.onchange = () => {
          toggleService(s, chk.checked);
        };
      }
    });

    // Toggle Password Visibility
    const pwdInput = modal.querySelector('#input-service-gmail');
    const pwdBtn = modal.querySelector('#btn-toggle-gmail-pwd');
    if (pwdBtn && pwdInput) {
      pwdBtn.onclick = () => {
        if (pwdInput.type === 'password') {
          pwdInput.type = 'text';
          pwdBtn.innerText = '🔒';
        } else {
          pwdInput.type = 'password';
          pwdBtn.innerText = '👁️';
        }
      };
    }

    // Test n8n Webhook
    const btnN8n = modal.querySelector('#btn-test-n8n');
    if (btnN8n) {
      btnN8n.onclick = () => {
        const urlInput = modal.querySelector('#input-service-n8n');
        testN8nWebhook(urlInput ? urlInput.value : '');
      };
    }

    // Quick Prompts Toggle
    const promptsToggle = modal.querySelector('#aitob-quick-prompts-toggle');
    const promptsDrawer = modal.querySelector('#aitob-quick-prompts-drawer');
    const promptsArrow = modal.querySelector('#aitob-prompts-arrow');
    if (promptsToggle && promptsDrawer) {
      promptsToggle.onclick = () => {
        const isOpen = promptsDrawer.classList.toggle('open');
        if (promptsArrow) promptsArrow.innerText = isOpen ? '▴' : '▾';
      };
    }

    // Prompt Chips
    modal.querySelectorAll('.aitob-chip').forEach(chip => {
      chip.onclick = () => {
        const text = chip.getAttribute('data-prompt');
        if (text) insertPromptIntoChat(text);
      };
    });

    // Skip Link
    const linkSkip = modal.querySelector('#link-setup-later');
    const chkSkip = modal.querySelector('#chk-skip-or-later');
    if (linkSkip && chkSkip) {
      linkSkip.onclick = () => {
        chkSkip.checked = true;
        closeConnectServicesModal();
      };
    }

    // Save & Continue Action
    const btnSave = modal.querySelector('#btn-save-continue');
    if (btnSave) {
      btnSave.onclick = () => {
        const newCfg = {
          db: modal.querySelector('#chk-service-db').checked,
          n8n: modal.querySelector('#chk-service-n8n').checked,
          line: modal.querySelector('#chk-service-line').checked,
          gmail: modal.querySelector('#chk-service-gmail').checked
        };
        saveIntegConfig(newCfg);

        // Store input values
        const dbVal = modal.querySelector('#input-service-db').value.trim();
        const n8nVal = modal.querySelector('#input-service-n8n').value.trim();
        const lineVal = modal.querySelector('#input-service-line').value.trim();
        const gmailVal = modal.querySelector('#input-service-gmail').value.trim();

        if (dbVal) localStorage.setItem(DB_CONFIG_KEY, dbVal);
        if (n8nVal) localStorage.setItem(N8N_WEBHOOK_KEY, n8nVal);
        if (lineVal) localStorage.setItem(LINE_TOKEN_KEY, lineVal);
        if (gmailVal) localStorage.setItem(GMAIL_CONFIG_KEY, gmailVal);

        localStorage.setItem(ONBOARDING_KEY, 'true');

        closeConnectServicesModal();
        showToast('🟢 บันทึกการเชื่อมต่อเรียบร้อย เริ่มต้นใช้งานได้ทันที!');

        // Focus chat input for seamless experience
        setTimeout(() => {
          const el = document.querySelector('#chat-textarea') || 
                     document.querySelector('textarea#chat-input') || 
                     document.querySelector('textarea');
          if (el) el.focus();
        }, 200);
      };
    }

    return overlay;
  }

  function openConnectServicesModal() {
    getOrCreateConnectModal();
    const overlay = document.getElementById('aitob-onboarding-overlay');
    if (overlay) overlay.classList.add('active');
  }

  function closeConnectServicesModal() {
    const overlay = document.getElementById('aitob-onboarding-overlay');
    if (overlay) overlay.classList.remove('active');
  }

  // 7. Sidebar & Header Trigger Elements
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
          <span style="font-weight: 600; font-size: 13.5px; color: #3b82f6; flex: 1;">เริ่มต้นใช้งาน</span>
          <span style="background: rgba(37, 99, 235, 0.12); color: #2563eb; font-size: 10px; font-weight: bold; padding: 1px 7px; border-radius: 6px; border: 1px solid rgba(37, 99, 235, 0.3);">Setup</span>
        `;
        btn.onclick = () => openConnectServicesModal();
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
      btn.innerHTML = `🚀 เชื่อมต่อระบบ`;
      btn.title = 'เปิดศูนย์ตั้งค่าการเชื่อมต่อบริการ (Connect Services)';
      btn.onclick = () => openConnectServicesModal();
      titleContainer.appendChild(btn);
    }
  }

  // 8. Auto-popup after registration/login when landing on chat dashboard
  let hasTriggeredAutoOpen = false;

  function checkFirstTimeUser() {
    try {
      if (hasTriggeredAutoOpen) return;
      if (window.location.pathname.startsWith('/auth')) return;

      const hasSeen = localStorage.getItem(ONBOARDING_KEY);
      if (hasSeen) return;

      const token = localStorage.getItem('token');
      const hasChatUI = document.querySelector('#chat-textarea') || 
                        document.querySelector('textarea#chat-input') || 
                        document.querySelector('textarea') || 
                        document.querySelector('#sidebar-new-chat-button') ||
                        document.querySelector('#sidebar-chats');

      // Trigger once user is authenticated and main chat dashboard is ready
      if (token || hasChatUI) {
        hasTriggeredAutoOpen = true;
        setTimeout(() => {
          openConnectServicesModal();
        }, 600);
      }
    } catch(e) {}
  }

  // Throttled lifecycle loop (every 1.5s)
  setInterval(() => {
    updateSidebarGetStarted();
    updateHeaderGetStarted();
    checkFirstTimeUser();
  }, 1500);

  // Init
  setTimeout(() => {
    getOrCreateConnectModal();
    updateSidebarGetStarted();
    updateHeaderGetStarted();
    checkFirstTimeUser();
  }, 800);
})();
