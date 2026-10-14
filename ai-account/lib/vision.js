import crypto from 'node:crypto';

export async function parseSlipOrInvoice({ imageBuffer, mimeType = 'image/jpeg', provider = 'gemini', options = {} }) {
  const base64Image = imageBuffer.toString('base64');
  const activeProvider = provider || process.env.AI_VISION_PROVIDER || 'gemini';

  try {
    if (activeProvider === 'gemini') {
      const apiKey = options.apiKey || process.env.GEMINI_API_KEY;
      if (!apiKey) return fallbackParse(base64Image, 'gemini (offline/mock)');
      return await parseWithGemini(base64Image, mimeType, apiKey);
    } else if (activeProvider === 'openai') {
      const apiKey = options.apiKey || process.env.OPENAI_API_KEY;
      if (!apiKey) return fallbackParse(base64Image, 'openai (offline/mock)');
      return await parseWithOpenAI(base64Image, mimeType, apiKey);
    } else if (activeProvider === 'slipok') {
      const apiKey = options.apiKey || process.env.SLIPOK_API_KEY;
      const branchId = options.branchId || process.env.SLIPOK_BRANCH_ID;
      if (!apiKey || !branchId) return fallbackParse(base64Image, 'slipok (offline/mock)');
      return await parseWithSlipOK(base64Image, options);
    } else if (activeProvider === 'offline' || activeProvider === 'mock') {
      return fallbackParse(base64Image, 'offline-heuristic');
    } else {
      return fallbackParse(base64Image, `${activeProvider} (fallback)`);
    }
  } catch (err) {
    console.warn(`[Vision] Provider ${activeProvider} failed: ${err.message}. Engaging smart offline fallback.`);
    return fallbackParse(base64Image, `${activeProvider} (fallback: ${err.message.slice(0, 30)})`);
  }
}

export function suggestCategory(parsed, categories = []) {
  const text = `${parsed.vendor_name || ''} ${parsed.sender_name || ''} ${parsed.receiver_name || ''} ${parsed.description || ''}`.toLowerCase();
  const docType = parsed.doc_type || 'slip';

  if (docType === 'slip' || docType === 'receipt') {
    if (text.includes('aws') || text.includes('google cloud') || text.includes('server') || text.includes('hosting') || text.includes('digitalocean')) {
      const found = categories.find(c => c.name.includes('เซิร์ฟเวอร์'));
      if (found) return found.id;
    }
    if (text.includes('facebook') || text.includes('ads') || text.includes('tiktok') || text.includes('โฆษณา')) {
      const found = categories.find(c => c.name.includes('โฆษณา'));
      if (found) return found.id;
    }
    if (text.includes('kerry') || text.includes('flash') || text.includes('ขนส่ง') || text.includes('ไปรษณีย์')) {
      const found = categories.find(c => c.name.includes('ขนส่ง'));
      if (found) return found.id;
    }
    if (text.includes('เช่า') || text.includes('rent') || text.includes('อาคาร')) {
      const found = categories.find(c => c.name.includes('เช่า'));
      if (found) return found.id;
    }
    if (text.includes('ปรึกษา') || text.includes('consult') || text.includes('บริการ') || text.includes('พัฒนาโปรแกรม')) {
      const found = categories.find(c => c.name.includes('บริการและที่ปรึกษา'));
      if (found) return found.id;
    }
    // Default income vs expense
    if (parsed.is_income ?? true) {
      const defIncome = categories.find(c => c.type === 'income');
      if (defIncome) return defIncome.id;
    } else {
      const defExp = categories.find(c => c.type === 'expense');
      if (defExp) return defExp.id;
    }
  }

  return categories[0]?.id || null;
}

export function autoCalculateTax(amount, docType = 'slip', whtRate = 0) {
  const baseAmount = Number(amount) || 0;
  // If invoice/receipt, default to VAT 7%
  const hasVat = docType === 'invoice' || docType === 'receipt';
  const vatAmount = hasVat ? Math.round(baseAmount * 0.07 * 100) / 100 : 0;
  const rate = Number(whtRate) || 0;
  const whtAmount = rate > 0 ? Math.round(baseAmount * (rate / 100) * 100) / 100 : 0;
  const netAmount = Math.round((baseAmount + vatAmount - whtAmount) * 100) / 100;

  return {
    baseAmount,
    vatAmount,
    whtRate: rate,
    whtAmount,
    netAmount
  };
}

function fallbackParse(base64Image, providerName) {
  const hash = crypto.createHash('sha256').update(base64Image).digest('hex').slice(0, 10).toUpperCase();
  const shortId = Math.floor(1000 + Math.random() * 9000);
  const now = new Date();
  const formattedTime = now.toISOString().replace('T', ' ').slice(0, 19);

  // Deterministic sample values using hash
  const amounts = [1250.00, 2500.00, 5000.00, 890.50, 15400.00, 3200.00];
  const charCode = hash.charCodeAt(0) % amounts.length;
  const sampleAmount = amounts[charCode];
  const banks = ['KBANK', 'SCB', 'BBL', 'KTB', 'TTB'];
  const bank = banks[hash.charCodeAt(1) % banks.length];

  return {
    doc_type: 'slip',
    amount: sampleAmount,
    transfer_time: formattedTime,
    reference_no: `SLIP-${hash}`,
    sender_bank: bank,
    sender_name: 'คุณ กิตติศักดิ์ เจริญสุข',
    receiver_bank: 'KBANK',
    receiver_name: 'บริษัท เอไอทูบี (ไทยแลนด์) จำกัด',
    receiver_account: 'xxx-2-89412-x',
    vendor_name: 'AItoB Private Cloud System',
    tax_id: '0105562098412',
    vat_amount: Math.round(sampleAmount * 0.07 * 100) / 100,
    confidence: 0.95,
    provider: providerName,
    is_offline_mock: true
  };
}

async function parseWithGemini(base64Image, mimeType, apiKey) {
  const prompt = `คุณคือผู้เชี่ยวชาญด้านบัญชีและการเงิน วิเคราะห์รูปภาพสลิปโอนเงิน หรือใบเสร็จ/ใบแจ้งหนี้ต่อไปนี้
สกัดข้อมูลให้ออกมาเป็น JSON เท่านั้นในรูปแบบ:
{
  "doc_type": "slip" | "invoice" | "receipt" | "unknown",
  "amount": number,
  "transfer_time": "YYYY-MM-DD HH:mm:ss" | null,
  "reference_no": string | null,
  "sender_bank": string | null,
  "sender_name": string | null,
  "receiver_bank": string | null,
  "receiver_name": string | null,
  "receiver_account": string | null,
  "vendor_name": string | null,
  "tax_id": string | null,
  "vat_amount": number | null,
  "confidence": number
}`;

  const res = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${apiKey}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contents: [{
        parts: [
          { text: prompt },
          { inline_data: { mime_type: mimeType, data: base64Image } }
        ]
      }],
      generationConfig: { response_mime_type: 'application/json' }
    })
  });

  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`Gemini API Error: ${res.status} - ${errText}`);
  }

  const data = await res.json();
  const text = data.candidates?.[0]?.content?.parts?.[0]?.text;
  const parsed = JSON.parse(text || '{}');
  parsed.provider = 'gemini';
  return parsed;
}

async function parseWithOpenAI(base64Image, mimeType, apiKey) {
  const res = await fetch('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`
    },
    body: JSON.stringify({
      model: 'gpt-4o-mini',
      response_format: { type: 'json_object' },
      messages: [
        {
          role: 'system',
          content: 'สกัดข้อมูลสลิปโอนเงินหรือใบเสร็จเป็น JSON: { doc_type, amount, transfer_time, reference_no, sender_bank, sender_name, receiver_bank, receiver_name, receiver_account, vendor_name, tax_id, vat_amount, confidence }'
        },
        {
          role: 'user',
          content: [
            { type: 'text', text: 'สกัดข้อมูลบัญชีจากภาพนี้' },
            { type: 'image_url', image_url: { url: `data:${mimeType};base64,${base64Image}` } }
          ]
        }
      ]
    })
  });

  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`OpenAI API Error: ${res.status} - ${errText}`);
  }

  const data = await res.json();
  const content = data.choices?.[0]?.message?.content;
  const parsed = JSON.parse(content || '{}');
  parsed.provider = 'openai';
  return parsed;
}

async function parseWithSlipOK(base64Image, options) {
  const apiKey = options.apiKey || process.env.SLIPOK_API_KEY;
  const branchId = options.branchId || process.env.SLIPOK_BRANCH_ID;
  if (!apiKey || !branchId) throw new Error('SlipOK API Key or Branch ID not configured');

  const res = await fetch(`https://api.slipok.com/api/line/apikey/${branchId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-authorization': apiKey
    },
    body: JSON.stringify({
      data: base64Image,
      log: true
    })
  });

  const json = await res.json();
  if (!json.success) {
    throw new Error(`SlipOK Error: ${json.message || 'Verification failed'}`);
  }

  const data = json.data;
  return {
    doc_type: 'slip',
    amount: data.amount,
    transfer_time: data.transDate + ' ' + (data.transTime || ''),
    reference_no: data.transRef,
    sender_bank: data.sendingBank,
    sender_name: data.sender?.name,
    receiver_bank: data.receivingBank,
    receiver_name: data.receiver?.name,
    receiver_account: data.receiver?.account?.value,
    confidence: 1.0,
    provider: 'slipok',
    raw: data
  };
}
