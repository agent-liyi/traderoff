import { describe, it, expect, vi } from 'vitest';

// We need to mock fs/promises mkdir and stream/promises pipeline
vi.mock('fs/promises', () => ({ mkdir: vi.fn().mockResolvedValue(undefined) }));
vi.mock('fs', () => ({ createWriteStream: vi.fn(() => ({ on: vi.fn() })) }));
vi.mock('stream/promises', () => ({ pipeline: vi.fn().mockResolvedValue(undefined) }));

import { POST } from '@/app/api/upload/route';

describe('API /api/upload', () => {
  it('缺少 file 时返回 400', async () => {
    const formData = new FormData();
    // No file appended
    const req = new Request('http://localhost/api/upload', {
      method: 'POST',
      body: formData,
    });

    const res = await POST(req as any);
    expect(res.status).toBe(400);
    const data = await res.json();
    expect(data.error).toBe('No file uploaded');
  });
});
