import { createClient } from '@libsql/client';

function getDbConfig() {
  const url = process.env.TURSO_DATABASE_URL;
  if (url) {
    return { url, authToken: process.env.TURSO_AUTH_TOKEN };
  }

  // 自部署模式（腾讯云 / 本地）：使用本地 SQLite 文件
  // Vercel 部署时会走上面的 Turso 分支
  const dbPath = process.env.SQLITE_DB_PATH || 'file:./data/podcast.db';
  return { url: dbPath };
}

const { url, authToken } = getDbConfig();

const db = createClient({
  url,
  authToken,
});

export default db;
