import http from 'node:http';
import assert from 'node:assert';
import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const serverPath = path.resolve(__dirname, '../server.js');
const TEST_PORT = 3101;

console.log('--- Starting ai-account Server for Integration Testing ---');
const serverProcess = spawn('node', [serverPath], {
  env: { ...process.env, PORT: TEST_PORT },
  stdio: 'pipe'
});

serverProcess.stdout.on('data', d => console.log('[Server stdout]', d.toString().trim()));
serverProcess.stderr.on('data', d => console.error('[Server stderr]', d.toString().trim()));

function request(method, pathName, body = null, headers = {}) {
  return new Promise((resolve, reject) => {
    const opts = {
      hostname: '127.0.0.1',
      port: TEST_PORT,
      path: pathName,
      method,
      headers: { ...headers }
    };
    if (body) {
      const dataStr = typeof body === 'string' ? body : JSON.stringify(body);
      opts.headers['Content-Type'] = 'application/json';
      opts.headers['Content-Length'] = Buffer.byteLength(dataStr);
    }
    const req = http.request(opts, res => {
      let data = '';
      res.on('data', c => { data += c; });
      res.on('end', () => {
        let json = null;
        try { json = JSON.parse(data); } catch(e){}
        resolve({ status: res.statusCode, headers: res.headers, body: json || data });
      });
    });
    req.on('error', reject);
    if (body) req.write(typeof body === 'string' ? body : JSON.stringify(body));
    req.end();
  });
}

// Wait for server to spin up
await new Promise(r => setTimeout(r, 1000));

try {
  console.log('1. Testing GET /api/summary');
  const sumRes = await request('GET', '/api/summary');
  assert.strictEqual(sumRes.status, 200);
  assert(sumRes.body.income !== undefined, 'Summary missing income');
  console.log('✓ Summary returns valid metrics:', sumRes.body);

  console.log('2. Testing GET /api/categories');
  const catRes = await request('GET', '/api/categories');
  assert.strictEqual(catRes.status, 200);
  assert(Array.isArray(catRes.body), 'Categories should be an array');
  assert(catRes.body.length > 0, 'Categories should not be empty');
  console.log(`✓ Categories loaded (${catRes.body.length} items)`);

  console.log('3. Testing POST /api/upload with mock slip');
  const dummyBase64 = Buffer.from('FAKE_SLIP_IMAGE_TEST_DATA').toString('base64');
  const uploadRes = await request('POST', '/api/upload', {
    imageBase64: dummyBase64,
    mimeType: 'image/jpeg',
    provider: 'offline',
    source: 'test-suite'
  });
  assert.strictEqual(uploadRes.status, 201);
  assert(uploadRes.body.transaction_id, 'Upload missing transaction_id');
  const txId = uploadRes.body.transaction_id;
  const refNo = uploadRes.body.parsed.reference_no;
  console.log(`✓ Upload successful, txId: ${txId}, ref: ${refNo}`);

  console.log('4. Testing Duplicate Prevention (Invariant)');
  const dupRes = await request('POST', '/api/upload', {
    imageBase64: dummyBase64,
    mimeType: 'image/jpeg',
    provider: 'offline',
    source: 'test-suite'
  });
  assert.strictEqual(dupRes.status, 409, 'Duplicate slip must return 409 Conflict');
  console.log('✓ Duplicate slip correctly blocked with 409 Conflict');

  console.log('5. Testing POST /api/transactions/:id/verify (Human-in-the-Loop HIL)');
  const verifyRes = await request('POST', `/api/transactions/${txId}/verify`, {
    amount: 5000,
    category_id: catRes.body[0].id,
    vat_amount: 350,
    wht_rate: 3,
    wht_amount: 150,
    net_amount: 5200,
    tax_id: '0105562098412',
    description: 'ทดสอบชำระค่าบริการผ่าน Test Suite',
    verified_notes: 'ตรวจสอบแล้วโดย Automation',
    verified_by: 'lead-auditor'
  });
  assert.strictEqual(verifyRes.status, 200);
  console.log('✓ Slip successfully verified with VAT/WHT/Audit notes');

  console.log('6. Testing GET /api/export/csv');
  const csvRes = await request('GET', '/api/export/csv');
  assert.strictEqual(csvRes.status, 200);
  assert(csvRes.headers['content-type'].includes('text/csv'), 'Content-Type should be text/csv');
  assert(csvRes.body.includes('ยอดก่อนภาษี') || csvRes.body.includes('0105562098412'), 'CSV should contain accounting headers & data');
  console.log('✓ CSV export generated with UTF-8 and proper Thai accounting columns');

  console.log('\n=======================================');
  console.log('🎉 ALL INTEGRATION TESTS PASSED 100%!');
  console.log('=======================================\n');
} finally {
  serverProcess.kill();
}

