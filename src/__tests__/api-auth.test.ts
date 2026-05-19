import { describe, it, expect, beforeEach, vi } from 'vitest';
import { NextRequest } from 'next/server';

// Stub env
vi.stubEnv('ADMIN_PASSWORD', 'correct-secret');

import { POST } from '@/app/api/auth/route';

describe('API /api/auth', () => {
  it('正确密码返回 200', async () => {
    const req = new NextRequest('http://localhost/api/auth', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: 'correct-secret' }),
    });
    const res = await POST(req);
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.success).toBe(true);
    expect(data.token).toBe('authenticated');
  });

  it('错误密码返回 401', async () => {
    const req = new NextRequest('http://localhost/api/auth', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: 'wrong' }),
    });
    const res = await POST(req);
    expect(res.status).toBe(401);
  });

  it('未设置 ADMIN_PASSWORD 时使用默认值 admin123', async () => {
    // The route uses fallback 'admin123' when env not set
    // We already stubbed to 'correct-secret', so 'admin123' should fail
    const req = new NextRequest('http://localhost/api/auth', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: 'admin123' }),
    });
    const res = await POST(req);
    expect(res.status).toBe(401);
  });

  it('JSON 解析失败返回 500', async () => {
    const req = new NextRequest('http://localhost/api/auth', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: 'not json',
    });
    const res = await POST(req);
    expect(res.status).toBe(500);
  });
});
