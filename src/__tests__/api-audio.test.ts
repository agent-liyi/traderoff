import { describe, it, expect, beforeEach, vi } from 'vitest';
import { NextRequest } from 'next/server';

const { mockDb } = vi.hoisted(() => ({ mockDb: { execute: vi.fn() } }));
vi.mock('@/lib/db', () => ({ default: mockDb }));

import { GET } from '@/app/api/audio/[id]/route';

describe('API /api/audio/[id]', () => {
  beforeEach(() => vi.clearAllMocks());

  it('返回音频二进制数据', async () => {
    const audioData = [0xff, 0xfb, 0x90, 0x00]; // MP3 frame header
    mockDb.execute.mockResolvedValueOnce({
      rows: [{ audio_data: audioData }],
    });

    const res = await GET(new NextRequest('http://localhost'), { params: { id: '1' } });
    expect(res.status).toBe(200);
    expect(res.headers.get('Content-Type')).toBe('audio/mpeg');
    expect(res.headers.get('Accept-Ranges')).toBe('bytes');

    const buffer = await res.arrayBuffer();
    expect(buffer.byteLength).toBe(4);
  });

  it('不存在返回 404', async () => {
    mockDb.execute.mockResolvedValueOnce({ rows: [] });
    const res = await GET(new NextRequest('http://localhost'), { params: { id: '999' } });
    expect(res.status).toBe(404);
  });

  it('audio_data 为空返回 404', async () => {
    mockDb.execute.mockResolvedValueOnce({ rows: [{ audio_data: null }] });
    const res = await GET(new NextRequest('http://localhost'), { params: { id: '1' } });
    expect(res.status).toBe(404);
  });

  it('DB 出错返回 500', async () => {
    mockDb.execute.mockRejectedValueOnce(new Error('boom'));
    const res = await GET(new NextRequest('http://localhost'), { params: { id: '1' } });
    expect(res.status).toBe(500);
  });
});
