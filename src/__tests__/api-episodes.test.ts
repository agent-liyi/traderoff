import { describe, it, expect, beforeEach, vi } from 'vitest';
import { NextRequest } from 'next/server';

// vi.mock is hoisted — must use vi.hoisted for factory variables
const { mockDb } = vi.hoisted(() => ({ mockDb: { execute: vi.fn() } }));
vi.mock('@/lib/db', () => ({ default: mockDb }));

import { GET, POST } from '@/app/api/episodes/route';

describe('API /api/episodes', () => {
  beforeEach(() => vi.clearAllMocks());

  describe('GET — 获取节目列表', () => {
    it('返回所有节目按 id DESC 排序', async () => {
      const rows = [
        { id: 2, episode_number: 'S1E02', title: '第二期', guest: '李四', description: null, transcript: null, cover_image: null, duration: null, publish_date: null, link_xiaoyuzhou: null, link_apple_podcasts: null, audio_url: null, created_at: '', updated_at: '' },
        { id: 1, episode_number: 'S1E01', title: '第一期', guest: '张三', description: null, transcript: null, cover_image: null, duration: null, publish_date: null, link_xiaoyuzhou: null, link_apple_podcasts: null, audio_url: null, created_at: '', updated_at: '' },
      ];
      mockDb.execute.mockResolvedValueOnce({ rows });

      const res = await GET();
      const data = await res.json();

      expect(res.status).toBe(200);
      expect(data).toHaveLength(2);
      expect(data[0].title).toBe('第二期');
    });

    it('DB 出错时返回 500 + []', async () => {
      mockDb.execute.mockRejectedValueOnce(new Error('boom'));
      const res = await GET();
      expect(res.status).toBe(500);
      expect(await res.json()).toEqual([]);
    });

    it('无节目返回 []', async () => {
      mockDb.execute.mockResolvedValueOnce({ rows: [] });
      const res = await GET();
      expect(res.status).toBe(200);
      expect(await res.json()).toEqual([]);
    });
  });

  describe('POST — 创建节目', () => {
    it('成功创建返回 201', async () => {
      const ep = { id: 3, episode_number: 'S1E03', title: '三期', guest: null, description: null, transcript: null, cover_image: null, duration: null, publish_date: null, link_xiaoyuzhou: null, link_apple_podcasts: null, audio_url: null, created_at: '', updated_at: '' };
      mockDb.execute.mockResolvedValueOnce({ rows: [] });
      mockDb.execute.mockResolvedValueOnce({ rows: [ep] });

      const req = new NextRequest('http://localhost/api/episodes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ episode_number: 'S1E03', title: '三期' }),
      });

      const res = await POST(req);
      expect(res.status).toBe(201);
      expect((await res.json()).title).toBe('三期');
    });

    it('DB 出错返回 500', async () => {
      mockDb.execute.mockRejectedValueOnce(new Error('write error'));
      const req = new NextRequest('http://localhost/api/episodes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ episode_number: 'S1E05', title: '五期' }),
      });
      const res = await POST(req);
      expect(res.status).toBe(500);
    });
  });
});
