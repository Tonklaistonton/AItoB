import { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const dataDir = path.resolve(__dirname, '../data');

if (!fs.existsSync(dataDir)) {
  fs.mkdirSync(dataDir, { recursive: true });
}

const dbPath = path.resolve(dataDir, 'account.db');
export const db = new DatabaseSync(dbPath);

export function initDatabase() {
  db.exec(`
    PRAGMA journal_mode = WAL;

    CREATE TABLE IF NOT EXISTS categories (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS transactions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
      category_id INTEGER,
      amount REAL NOT NULL,
      vat_amount REAL DEFAULT 0,
      wht_rate REAL DEFAULT 0,
      wht_amount REAL DEFAULT 0,
      net_amount REAL DEFAULT 0,
      status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'verified', 'rejected')),
      reference_no TEXT UNIQUE,
      tax_id TEXT,
      description TEXT,
      source TEXT NOT NULL DEFAULT 'manual',
      source_ref_id TEXT,
      image_path TEXT,
      image_data TEXT,
      sender_bank TEXT,
      sender_name TEXT,
      receiver_bank TEXT,
      receiver_name TEXT,
      receiver_account TEXT,
      raw_ai_payload TEXT,
      verified_by TEXT,
      verified_at DATETIME,
      verified_notes TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (category_id) REFERENCES categories (id)
    );

    CREATE TABLE IF NOT EXISTS system_config (
      key TEXT PRIMARY KEY,
      value TEXT NOT NULL
    );
  `);

  // Migrate columns if upgrading from earlier version
  const cols = [
    { name: 'vat_amount', type: 'REAL DEFAULT 0' },
    { name: 'wht_rate', type: 'REAL DEFAULT 0' },
    { name: 'wht_amount', type: 'REAL DEFAULT 0' },
    { name: 'net_amount', type: 'REAL DEFAULT 0' },
    { name: 'tax_id', type: 'TEXT' },
    { name: 'image_data', type: 'TEXT' },
    { name: 'sender_bank', type: 'TEXT' },
    { name: 'sender_name', type: 'TEXT' },
    { name: 'receiver_bank', type: 'TEXT' },
    { name: 'receiver_name', type: 'TEXT' },
    { name: 'receiver_account', type: 'TEXT' },
    { name: 'verified_notes', type: 'TEXT' }
  ];

  for (const col of cols) {
    try {
      db.exec(`ALTER TABLE transactions ADD COLUMN ${col.name} ${col.type};`);
    } catch {
      // Column already exists, ignore
    }
  }

  // Default categories
  const count = db.prepare('SELECT COUNT(*) as c FROM categories').get();
  if (count.c === 0) {
    const insert = db.prepare('INSERT INTO categories (name, type) VALUES (?, ?)');
    const defaultCategories = [
      ['ขายสินค้า/บริการ', 'income'],
      ['บริการที่ปรึกษา/ไอที', 'income'],
      ['รายได้อื่นๆ', 'income'],
      ['ค่าบริการและที่ปรึกษา (หัก 3%)', 'expense'],
      ['ค่าเช่าสถานที่/อาคาร (หัก 5%)', 'expense'],
      ['ค่าขนส่งและโลจิสติกส์ (หัก 1%)', 'expense'],
      ['ค่าโฆษณาและการตลาด (หัก 2%)', 'expense'],
      ['ค่าเซิร์ฟเวอร์/คลาวด์/เครื่องมือ', 'expense'],
      ['ค่าอุปกรณ์และวัสดุสำนักงาน', 'expense'],
      ['ค่าใช้จ่ายเบ็ดเตล็ด', 'expense']
    ];
    for (const [name, type] of defaultCategories) {
      insert.run(name, type);
    }
  }
}
