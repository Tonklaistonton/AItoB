import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { db, initDatabase } from './lib/db.js';
import { parseSlipOrInvoice, suggestCategory, autoCalculateTax } from './lib/vision.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Native environment file loading without external dependencies
const envFile = path.resolve(__dirname, '.env');
if (fs.existsSync(envFile) && typeof process.loadEnvFile === 'function') {
  process.loadEnvFile(envFile);
}

const PORT = process.env.PORT || 3001;

initDatabase();

function sendJson(res, status, data) {
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization'
  });
  res.end(JSON.stringify(data));
}

function parseJsonBody(req, limitBytes = 25 * 1024 * 1024) {
  return new Promise((resolve, reject) => {
    let body = '';
    let size = 0;
    req.on('data', chunk => {
      size += chunk.length;
      if (size > limitBytes) {
        reject(new Error('Payload too large (Max 25MB)'));
      }
      body += chunk;
    });
    req.on('end', () => {
      try {
        resolve(JSON.parse(body || '{}'));
      } catch (err) {
        reject(new Error('Invalid JSON format'));
      }
    });
    req.on('error', reject);
  });
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);

  if (req.method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization'
    });
    return res.end();
  }

  // Dashboard Summary API with VAT/WHT
  if (req.method === 'GET' && url.pathname === '/api/summary') {
    const income = db.prepare("SELECT COALESCE(SUM(amount), 0) as total, COALESCE(SUM(vat_amount), 0) as vat_output FROM transactions WHERE type='income' AND status='verified'").get();
    const expense = db.prepare("SELECT COALESCE(SUM(amount), 0) as total, COALESCE(SUM(vat_amount), 0) as vat_input, COALESCE(SUM(wht_amount), 0) as wht_total FROM transactions WHERE type='expense' AND status='verified'").get();
    const pending = db.prepare("SELECT COUNT(*) as count, COALESCE(SUM(amount), 0) as total FROM transactions WHERE status='pending'").get();
    const verifiedCount = db.prepare("SELECT COUNT(*) as count FROM transactions WHERE status='verified'").get();
    const rejectedCount = db.prepare("SELECT COUNT(*) as count FROM transactions WHERE status='rejected'").get();

    return sendJson(res, 200, {
      income: income.total,
      expense: expense.total,
      net: income.total - expense.total,
      pendingCount: pending.count,
      pendingTotal: pending.total,
      verifiedCount: verifiedCount.count,
      rejectedCount: rejectedCount.count,
      vatOutput: income.vat_output,
      vatInput: expense.vat_input,
      netVatPayable: income.vat_output - expense.vat_input,
      whtTotal: expense.wht_total
    });
  }

  // List Categories
  if (req.method === 'GET' && url.pathname === '/api/categories') {
    const categories = db.prepare('SELECT * FROM categories ORDER BY type, id').all();
    return sendJson(res, 200, categories);
  }

  // List Transactions
  if (req.method === 'GET' && url.pathname === '/api/transactions') {
    const status = url.searchParams.get('status') || 'all';
    const categoryId = url.searchParams.get('category_id');
    const type = url.searchParams.get('type');

    let query = 'SELECT t.*, c.name as category_name FROM transactions t LEFT JOIN categories c ON t.category_id = c.id WHERE 1=1';
    let params = [];

    if (status !== 'all') {
      query += ' AND t.status = ?';
      params.push(status);
    }
    if (categoryId) {
      query += ' AND t.category_id = ?';
      params.push(categoryId);
    }
    if (type) {
      query += ' AND t.type = ?';
      params.push(type);
    }
    query += ' ORDER BY t.created_at DESC LIMIT 200';

    const rows = db.prepare(query).all(...params);
    return sendJson(res, 200, rows);
  }

  // Get Single Transaction Detail
  if (req.method === 'GET' && url.pathname.startsWith('/api/transactions/') && !url.pathname.endsWith('/verify') && !url.pathname.endsWith('/reject')) {
    const id = url.pathname.split('/')[3];
    const item = db.prepare('SELECT t.*, c.name as category_name FROM transactions t LEFT JOIN categories c ON t.category_id = c.id WHERE t.id = ?').get(id);
    if (!item) return sendJson(res, 404, { error: 'Transaction not found' });
    return sendJson(res, 200, item);
  }

  // Upload Slip / Invoice directly via UI
  if (req.method === 'POST' && (url.pathname === '/api/upload' || url.pathname === '/api/webhook/slip')) {
    try {
      const payload = await parseJsonBody(req);
      let { imageBase64, mimeType = 'image/jpeg', source = 'manual', sourceRefId, provider } = payload;

      if (!imageBase64) {
        return sendJson(res, 400, { error: 'imageBase64 is required' });
      }

      // Format Data URL if raw base64
      let dataUrl = imageBase64;
      if (!imageBase64.startsWith('data:')) {
        dataUrl = `data:${mimeType};base64,${imageBase64}`;
      } else {
        const matches = imageBase64.match(/^data:([a-zA-Z0-9]+\/[a-zA-Z0-9-.+]+);base64,(.+)$/);
        if (matches) {
          mimeType = matches[1];
          imageBase64 = matches[2];
        }
      }

      const buffer = Buffer.from(imageBase64, 'base64');
      const activeProvider = provider || process.env.AI_VISION_PROVIDER || 'gemini';

      // Parse with Vision engine (with offline mock fallback)
      const parsed = await parseSlipOrInvoice({
        imageBuffer: buffer,
        mimeType,
        provider: activeProvider
      });

      // Check duplicate reference
      if (parsed.reference_no) {
        const existing = db.prepare('SELECT id FROM transactions WHERE reference_no = ?').get(parsed.reference_no);
        if (existing) {
          return sendJson(res, 409, { error: 'Duplicate transaction (สลิปนี้เคยบันทึกในระบบแล้ว)', reference_no: parsed.reference_no, existing_id: existing.id });
        }
      }

      const isIncome = parsed.doc_type === 'slip' || parsed.doc_type === 'receipt';
      const type = isIncome ? 'income' : 'expense';

      // Auto-suggest category
      const allCategories = db.prepare('SELECT * FROM categories').all();
      const suggestedCatId = suggestCategory({ ...parsed, is_income: isIncome }, allCategories);

      // Auto-calculate tax defaults
      const taxCalc = autoCalculateTax(parsed.amount || 0, parsed.doc_type, 0);

      const description = parsed.description || (parsed.doc_type === 'slip'
        ? `สลิปโอน: ${parsed.sender_name || 'ลูกค้า'} -> ${parsed.receiver_name || 'บริษัท'}`
        : `เอกสาร: ${parsed.vendor_name || 'คู่ค้า'} (${parsed.doc_type || 'ใบแจ้งหนี้'})`);

      const insert = db.prepare(`
        INSERT INTO transactions (
          type, category_id, amount, vat_amount, wht_rate, wht_amount, net_amount,
          status, reference_no, tax_id, description, source, source_ref_id,
          image_data, sender_bank, sender_name, receiver_bank, receiver_name,
          receiver_account, raw_ai_payload
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `);

      const result = insert.run(
        type,
        suggestedCatId,
        parsed.amount || 0,
        parsed.vat_amount || taxCalc.vatAmount || 0,
        0,
        0,
        taxCalc.netAmount || parsed.amount || 0,
        parsed.reference_no || null,
        parsed.tax_id || null,
        description,
        source,
        sourceRefId || null,
        dataUrl,
        parsed.sender_bank || null,
        parsed.sender_name || null,
        parsed.receiver_bank || null,
        parsed.receiver_name || null,
        parsed.receiver_account || null,
        JSON.stringify(parsed)
      );

      return sendJson(res, 201, {
        success: true,
        transaction_id: Number(result.lastInsertRowid),
        suggested_category_id: suggestedCatId,
        parsed
      });
    } catch (err) {
      console.error('[Upload Error]', err);
      return sendJson(res, 500, { error: err.message });
    }
  }

  // Confirm/Verify transaction with VAT/WHT/Category update (Human-in-the-loop)
  if (req.method === 'POST' && url.pathname.startsWith('/api/transactions/') && url.pathname.endsWith('/verify')) {
    const id = url.pathname.split('/')[3];
    try {
      const payload = await parseJsonBody(req);
      const {
        amount,
        category_id,
        vat_amount = 0,
        wht_rate = 0,
        wht_amount = 0,
        net_amount,
        tax_id,
        description,
        verified_notes,
        verified_by = 'admin'
      } = payload;

      const calcNet = net_amount !== undefined
        ? Number(net_amount)
        : (Number(amount) + Number(vat_amount) - Number(wht_amount));

      const update = db.prepare(`
        UPDATE transactions
        SET status = 'verified',
            amount = COALESCE(?, amount),
            category_id = COALESCE(?, category_id),
            vat_amount = ?,
            wht_rate = ?,
            wht_amount = ?,
            net_amount = ?,
            tax_id = COALESCE(?, tax_id),
            description = COALESCE(?, description),
            verified_notes = ?,
            verified_by = ?,
            verified_at = CURRENT_TIMESTAMP
        WHERE id = ?
      `);

      update.run(
        amount !== undefined ? Number(amount) : null,
        category_id ? Number(category_id) : null,
        Number(vat_amount) || 0,
        Number(wht_rate) || 0,
        Number(wht_amount) || 0,
        calcNet,
        tax_id || null,
        description || null,
        verified_notes || null,
        verified_by,
        id
      );

      return sendJson(res, 200, { success: true, id: Number(id) });
    } catch (err) {
      return sendJson(res, 500, { error: err.message });
    }
  }

  // Reject transaction
  if (req.method === 'POST' && url.pathname.startsWith('/api/transactions/') && url.pathname.endsWith('/reject')) {
    const id = url.pathname.split('/')[3];
    try {
      const update = db.prepare("UPDATE transactions SET status = 'rejected' WHERE id = ?");
      update.run(id);
      return sendJson(res, 200, { success: true, id: Number(id) });
    } catch (err) {
      return sendJson(res, 500, { error: err.message });
    }
  }

  // Export to CSV for Excel & Express
  if (req.method === 'GET' && url.pathname === '/api/export/csv') {
    const rows = db.prepare(`
      SELECT t.id, t.created_at, t.type, c.name as category, t.amount, t.vat_amount,
             t.wht_rate, t.wht_amount, t.net_amount, t.reference_no, t.tax_id,
             t.sender_bank, t.sender_name, t.receiver_bank, t.receiver_name,
             t.description, t.status, t.verified_by, t.verified_at
      FROM transactions t
      LEFT JOIN categories c ON t.category_id = c.id
      ORDER BY t.created_at DESC
    `).all();

    const headers = [
      'ID', 'วัน-เวลา', 'ประเภท', 'หมวดหมู่บัญชี', 'ยอดก่อนภาษี', 'VAT 7%',
      'อัตราหัก ณ ที่จ่าย %', 'ยอดหัก ณ ที่จ่าย', 'ยอดสุทธิ', 'เลขอ้างอิงสลิป',
      'เลขประจำตัวผู้เสียภาษี', 'ธนาคารต้นทาง', 'ผู้โอน', 'ธนาคารปลายทาง',
      'ผู้รับ', 'รายละเอียด', 'สถานะ', 'ผู้ตรวจสอบ', 'เวลายืนยัน'
    ];

    const escapeCsv = (val) => {
      if (val === null || val === undefined) return '""';
      const str = String(val).replace(/"/g, '""');
      return `"${str}"`;
    };

    let csv = '\uFEFF'; // UTF-8 BOM for Excel Thai compatibility
    csv += headers.map(escapeCsv).join(',') + '\r\n';

    for (const r of rows) {
      const line = [
        r.id,
        r.created_at,
        r.type === 'income' ? 'รายรับ' : 'รายจ่าย',
        r.category || '-',
        Number(r.amount).toFixed(2),
        Number(r.vat_amount || 0).toFixed(2),
        r.wht_rate ? `${r.wht_rate}%` : '0%',
        Number(r.wht_amount || 0).toFixed(2),
        Number(r.net_amount || r.amount).toFixed(2),
        r.reference_no || '-',
        r.tax_id || '-',
        r.sender_bank || '-',
        r.sender_name || '-',
        r.receiver_bank || '-',
        r.receiver_name || '-',
        r.description || '-',
        r.status,
        r.verified_by || '-',
        r.verified_at || '-'
      ];
      csv += line.map(escapeCsv).join(',') + '\r\n';
    }

    const filename = `aitob-accounting-${new Date().toISOString().slice(0, 10)}.csv`;
    res.writeHead(200, {
      'Content-Type': 'text/csv; charset=utf-8',
      'Content-Disposition': `attachment; filename="${filename}"`,
      'Access-Control-Allow-Origin': '*'
    });
    return res.end(csv);
  }

  // Static files / Dashboard HTML
  if (req.method === 'GET' && (url.pathname === '/' || url.pathname === '/index.html')) {
    const htmlPath = path.resolve(__dirname, 'public/index.html');
    if (fs.existsSync(htmlPath)) {
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      return fs.createReadStream(htmlPath).pipe(res);
    }
  }

  sendJson(res, 404, { error: 'Not Found' });
});

server.listen(PORT, () => {
  console.log(`[ai-account] Server running on http://localhost:${PORT}`);
});
