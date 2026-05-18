'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { Episode } from '@/lib/types';

export default function AdminPage() {
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchEpisodes = async () => {
    const res = await fetch('/api/episodes');
    if (res.ok) {
      const data = await res.json();
      setEpisodes(data);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchEpisodes();
  }, []);

  const handleDelete = async (id: number) => {
    if (!confirm('确定要删除这期节目吗？')) return;

    const res = await fetch(`/api/episodes/${id}`, { method: 'DELETE' });
    if (res.ok) {
      setEpisodes(episodes.filter((e) => e.id !== id));
    }
  };

  if (loading) {
    return <p className="text-muted">加载中...</p>;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold">节目管理</h1>
        <Link
          href="/admin/new"
          className="px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-amber-700 transition-colors"
        >
          + 新建节目
        </Link>
      </div>

      {episodes.length === 0 ? (
        <div className="text-center py-16">
          <p className="text-muted mb-4">还没有节目</p>
          <Link href="/admin/new" className="text-accent hover:underline">
            创建第一期节目 →
          </Link>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-stone-200 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-stone-200 text-left text-sm text-muted">
                <th className="px-4 py-3 font-medium">期数</th>
                <th className="px-4 py-3 font-medium">标题</th>
                <th className="px-4 py-3 font-medium">嘉宾</th>
                <th className="px-4 py-3 font-medium">日期</th>
                <th className="px-4 py-3 font-medium">时长</th>
                <th className="px-4 py-3 font-medium text-right">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100">
              {episodes.map((episode) => (
                <tr key={episode.id} className="hover:bg-stone-50">
                  <td className="px-4 py-3 text-sm font-mono">
                    {episode.episode_number}
                  </td>
                  <td className="px-4 py-3 text-sm font-medium">
                    {episode.title}
                  </td>
                  <td className="px-4 py-3 text-sm text-muted">
                    {episode.guest || '-'}
                  </td>
                  <td className="px-4 py-3 text-sm text-muted">
                    {episode.publish_date}
                  </td>
                  <td className="px-4 py-3 text-sm text-muted">
                    {episode.duration}
                  </td>
                  <td className="px-4 py-3 text-sm text-right">
                    <Link
                      href={`/admin/episodes/${episode.id}/edit`}
                      className="text-accent hover:underline mr-3"
                    >
                      编辑
                    </Link>
                    <button
                      onClick={() => handleDelete(episode.id)}
                      className="text-red-500 hover:underline"
                    >
                      删除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
