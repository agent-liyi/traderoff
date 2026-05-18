import { createClient } from '@libsql/client';

function getDbUrl(): string {
  const url = process.env.TURSO_DATABASE_URL;
  if (url) return url;

  // 仅本地开发时 fallback 到本地文件
  if (process.env.NODE_ENV === 'development') {
    return 'file:./data/podcast.db';
  }

  throw new Error(
    'TURSO_DATABASE_URL is not set. Add it to Vercel Environment Variables and redeploy.'
  );
}

const db = createClient({
  url: getDbUrl(),
  authToken: process.env.TURSO_AUTH_TOKEN,
});

export default db;
