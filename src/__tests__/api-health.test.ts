import { describe, it, expect, beforeEach, vi } from 'vitest';

// Mock @libsql/client
vi.mock('@libsql/client', () => ({
  createClient: vi.fn(() => ({
    execute: vi.fn().mockResolvedValue({ rows: [{ count: 3 }] }),
    close: vi.fn(),
  })),
}));

// Stub env
vi.stubEnv('TURSO_DATABASE_URL', 'libsql://test-db.turso.io');
vi.stubEnv('TURSO_AUTH_TOKEN', 'test-token');
vi.stubEnv('ADMIN_PASSWORD', 'test123');

import { GET } from '@/app/api/health/route';

describe('API /api/health', () => {
  it('返回环境变量及 DB 连接状态', async () => {
    const res = await GET();
    const data = await res.json();

    expect(data.node_env).toBe('test');
    expect(data.env_url).toContain('set');
    expect(data.env_token).toContain('set');
    expect(data.env_admin_pw).toBe('set');
    expect(data.db_connected).toBe(true);
    expect(data.episode_count).toBe(3);
    expect(res.status).toBe(200);
  });
});
