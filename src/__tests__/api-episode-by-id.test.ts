import { describe, it, expect, beforeEach, vi } from 'vitest';
import { NextRequest } from 'next/server';

const { mockDb } = vi.hoisted(() => ({ mockDb: { execute: vi.fn() } }));
vi.mock('@/lib/db', () => ({ default: mockDb }));

import { GET, PUT, DELETE } from '@/app/api/episodes/[id]/route';

const params = { id: '1' };
const mockEpisode = {
  id: 1, episode_number: 'S1E01', title: '第一期', guest: null, description: null, transcript: null, cover_image: null, duration: null, publish_date: null, link_xiaoyuzhou: null, link_apple_podcasts: null, audio_url: null, created_at: '', updated_at: '',
};

describe('API /api/episodes/[id]', () => {
  beforeEach(() => vi.clearAllMocks());

  describe('GET', () => {
    it('返回节目详情', async () => {
      mockDb.execute.mockResolvedValueOnce({ rows: [mockEpisode] });
      const res = await GET(new NextRequest('http://localhost'), { params });
      expect(res.status).toBe(200);
      expect((await res.json()).title).toBe('第一期');
    });

    it('不存在返回 404', async () => {
      mockDb.execute.mockResolvedValueOnce({ rows: [] });
      const res = await GET(new NextRequest('http://localhost'), { params });
      expect(res.status).toBe(404);
    });

    it('DB 出错返回 500', async () => {
      mockDb.execute.mockRejectedValueOnce(new Error('boom'));
      const res = await GET(new NextRequest('http://localhost'), { params });
      expect(res.status).toBe(500);
    });
  });

  describe('PUT', () => {
    it('成功更新节目', async () => {
      mockDb.execute.mockResolvedValueOnce({ rows: [] });
      mockDb.execute.mockResolvedValueOnce({ rows: [{ ...mockEpisode, title: '更新后' }] });

      const req = new NextRequest('http://localhost/api/episodes/1', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ episode_number: 'S1E01', title: '更新后' }),
      });

      const res = await PUT(req, { params });
      expect(res.status).toBe(200);
      expect((await res.json()).title).toBe('更新后');
    });

    it('DB 出错返回 500', async () => {
      mockDb.execute.mockRejectedValueOnce(new Error('boom'));
      const req = new NextRequest('http://localhost', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ episode_number: 'S1E01', title: 'x' }),
      });
      const res = await PUT(req, { params });
      expect(res.status).toBe(500);
    });
  });

  describe('DELETE', () => {
    it('成功删除返回 200', async () => {
      mockDb.execute.mockResolvedValueOnce({ rows: [] });
      const res = await DELETE(new NextRequest('http://localhost'), { params });
      expect(res.status).toBe(200);
      expect(await res.json()).toEqual({ success: true });
    });

    it('DB 出错返回 500', async () => {
      mockDb.execute.mockRejectedValueOnce(new Error('boom'));
      const res = await DELETE(new NextRequest('http://localhost'), { params });
      expect(res.status).toBe(500);
    });
  });
});
