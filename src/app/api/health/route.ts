import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET() {
  const checks: Record<string, unknown> = {
    node_env: process.env.NODE_ENV,
    env_url: process.env.TURSO_DATABASE_URL ? `set (${process.env.TURSO_DATABASE_URL.slice(0, 30)}...)` : 'NOT SET',
    env_token: process.env.TURSO_AUTH_TOKEN ? `set (${process.env.TURSO_AUTH_TOKEN.slice(0, 10)}...)` : 'NOT SET',
    env_admin_pw: process.env.ADMIN_PASSWORD ? 'set' : 'NOT SET',
  };

  try {
    const { createClient } = await import('@libsql/client');
    const url = process.env.TURSO_DATABASE_URL;
    if (!url) {
      checks.db_connected = false;
      checks.db_error = 'TURSO_DATABASE_URL not set, cannot connect';
      return NextResponse.json(checks, { status: 500 });
    }
    const client = createClient({ url, authToken: process.env.TURSO_AUTH_TOKEN });
    const result = await client.execute('SELECT COUNT(*) as count FROM episodes');
    checks.db_connected = true;
    checks.episode_count = result.rows[0]?.count ?? 0;
  } catch (e: unknown) {
    checks.db_connected = false;
    checks.db_error = e instanceof Error ? e.message : String(e);
  }

  const status = checks.db_connected ? 200 : 500;
  return NextResponse.json(checks, { status });
}
