import { NextResponse } from 'next/server';
import db from '@/lib/db';

export const dynamic = 'force-dynamic';

export async function GET() {
  const checks: Record<string, unknown> = {
    env_url: process.env.TURSO_DATABASE_URL ? 'set' : 'NOT SET',
    env_token: process.env.TURSO_AUTH_TOKEN ? 'set' : 'NOT SET',
  };

  try {
    const result = await db.execute('SELECT COUNT(*) as count FROM episodes');
    checks.db_connected = true;
    checks.episode_count = result.rows[0]?.count ?? 0;
  } catch (e: unknown) {
    checks.db_connected = false;
    checks.db_error = e instanceof Error ? e.message : String(e);
  }

  return NextResponse.json(checks);
}
