import { createClient } from '@libsql/client';
import fs from 'fs';
import path from 'path';
import dotenv from 'dotenv';

// 加载 .env.local
const envPath = path.join(process.cwd(), '.env.local');
if (fs.existsSync(envPath)) {
  dotenv.config({ path: envPath });
}

async function main() {
  // 确保本地 data/ 目录存在（本地文件模式需要）
  const dataDir = path.join(process.cwd(), 'data');
  if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir, { recursive: true });
  }

  const db = createClient({
    url: process.env.TURSO_DATABASE_URL || 'file:./data/podcast.db',
    authToken: process.env.TURSO_AUTH_TOKEN,
  });

  await db.execute(`
    CREATE TABLE IF NOT EXISTS episodes (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      episode_number TEXT NOT NULL,
      title TEXT NOT NULL,
      guest TEXT,
      description TEXT,
      transcript TEXT,
      cover_image TEXT,
      duration TEXT,
      publish_date TEXT,
      link_xiaoyuzhou TEXT,
      link_apple_podcasts TEXT,
      audio_url TEXT,
      audio_data BLOB,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
  `);

  // 兼容旧表：如果 audio_data 列不存在则添加
  try {
    await db.execute(`ALTER TABLE episodes ADD COLUMN audio_data BLOB`);
    console.log('   ➕ 已添加 audio_data BLOB 列');
  } catch {
    // 列已存在，忽略
  }

  console.log('✅ Database initialized successfully');
  console.log(`   URL: ${process.env.TURSO_DATABASE_URL || 'file:./data/podcast.db'}`);

  db.close();
}

main().catch((err) => {
  console.error('❌ Failed to initialize database:', err);
  process.exit(1);
});
