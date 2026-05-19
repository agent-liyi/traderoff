import { describe, it, expect, vi } from 'vitest';

import { POST } from '@/app/api/upload/route';

describe('API /api/upload', () => {
  it('缺少 file 时返回 400', async () => {
    const formData = new FormData();
    const req = new Request('http://localhost/api/upload', {
      method: 'POST',
      body: formData,
    });

    const res = await POST(req as any);
    expect(res.status).toBe(400);
    const data = await res.json();
    expect(data.error).toBe('未选择文件');
  });
});
