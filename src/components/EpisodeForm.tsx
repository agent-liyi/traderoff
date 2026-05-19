'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import RichTextEditor from './RichTextEditor';
import { Episode } from '@/lib/types';

interface EpisodeFormProps {
  episode?: Episode;
}

export default function EpisodeForm({ episode }: EpisodeFormProps) {
  const router = useRouter();
  const [saving, setSaving] = useState(false);
  const [coverPreview, setCoverPreview] = useState(episode?.cover_image || '');
  const [audioFileName, setAudioFileName] = useState('');
  const [audioUploading, setAudioUploading] = useState(false);

  const [form, setForm] = useState({
    episode_number: episode?.episode_number || '',
    title: episode?.title || '',
    guest: episode?.guest || '',
    duration: episode?.duration || '',
    publish_date: episode?.publish_date || '',
    cover_image: episode?.cover_image || '',
    description: episode?.description || '',
    transcript: episode?.transcript || '',
    link_xiaoyuzhou: episode?.link_xiaoyuzhou || '',
    link_apple_podcasts: episode?.link_apple_podcasts || '',
    audio_url: episode?.audio_url || '',
    audio_path: '',
  });

  const handleChange = (field: string, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });

      const data = await res.json();
      if (res.ok) {
        const filename = data.path.split('/').pop();
        const mediaUrl = `/api/media/${filename}`;
        setForm((prev) => ({ ...prev, cover_image: mediaUrl }));
        setCoverPreview(mediaUrl);
      } else {
        alert(`图片上传失败: ${data.error || '未知错误'}`);
      }
    } catch (err: any) {
      alert(`图片上传失败: ${err.message || '网络错误'}`);
    }
  };

  const handleAudioUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setAudioUploading(true);
    setAudioFileName(file.name);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });

      const data = await res.json();
      if (res.ok) {
        handleChange('audio_path', data.path);
        handleChange('audio_url', '');
      } else {
        alert(`音频上传失败: ${data.error || '未知错误'}`);
        setAudioFileName('');
      }
    } catch (err: any) {
      alert(`音频上传失败: ${err.message || '网络错误'}`);
      setAudioFileName('');
    }

    setAudioUploading(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);

    const url = episode ? `/api/episodes/${episode.id}` : '/api/episodes';
    const method = episode ? 'PUT' : 'POST';

    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    });

    if (res.ok) {
      router.push('/admin');
      router.refresh();
    } else {
      alert('保存失败');
    }

    setSaving(false);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6 max-w-4xl">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Episode Number */}
        <div>
          <label className="block text-sm font-medium mb-2">期数</label>
          <input
            type="text"
            value={form.episode_number}
            onChange={(e) => handleChange('episode_number', e.target.value)}
            placeholder="S1E01"
            required
            className="w-full px-4 py-2.5 border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent/50"
          />
        </div>

        {/* Title */}
        <div>
          <label className="block text-sm font-medium mb-2">标题</label>
          <input
            type="text"
            value={form.title}
            onChange={(e) => handleChange('title', e.target.value)}
            placeholder="节目标题"
            required
            className="w-full px-4 py-2.5 border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent/50"
          />
        </div>

        {/* Guest */}
        <div>
          <label className="block text-sm font-medium mb-2">嘉宾</label>
          <input
            type="text"
            value={form.guest}
            onChange={(e) => handleChange('guest', e.target.value)}
            placeholder="嘉宾姓名"
            className="w-full px-4 py-2.5 border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent/50"
          />
        </div>

        {/* Duration */}
        <div>
          <label className="block text-sm font-medium mb-2">时长</label>
          <input
            type="text"
            value={form.duration}
            onChange={(e) => handleChange('duration', e.target.value)}
            placeholder="57:59"
            className="w-full px-4 py-2.5 border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent/50"
          />
        </div>

        {/* Publish Date */}
        <div>
          <label className="block text-sm font-medium mb-2">发布日期</label>
          <input
            type="text"
            value={form.publish_date}
            onChange={(e) => handleChange('publish_date', e.target.value)}
            placeholder="2026/05/14"
            className="w-full px-4 py-2.5 border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent/50"
          />
        </div>

        {/* Cover Image */}
        <div>
          <label className="block text-sm font-medium mb-2">封面图</label>
          <input
            type="file"
            accept="image/*"
            onChange={handleImageUpload}
            className="w-full px-4 py-2.5 border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent/50 text-sm"
          />
          {coverPreview && (
            <img
              src={coverPreview}
              alt="Cover preview"
              className="mt-2 w-24 h-24 object-cover rounded-lg"
            />
          )}
        </div>
      </div>

      {/* Links */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <label className="block text-sm font-medium mb-2">
            小宇宙链接
          </label>
          <input
            type="url"
            value={form.link_xiaoyuzhou}
            onChange={(e) => handleChange('link_xiaoyuzhou', e.target.value)}
            placeholder="https://www.xiaoyuzhoufm.com/episode/..."
            className="w-full px-4 py-2.5 border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent/50"
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-2">
            苹果播客链接
          </label>
          <input
            type="url"
            value={form.link_apple_podcasts}
            onChange={(e) =>
              handleChange('link_apple_podcasts', e.target.value)
            }
            placeholder="https://podcasts.apple.com/..."
            className="w-full px-4 py-2.5 border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent/50"
          />
        </div>
        <div className="md:col-span-2">
          <label className="block text-sm font-medium mb-2">
            音频文件
          </label>
          <div className="space-y-3">
            {/* 文件上传 */}
            <div className="flex items-center gap-3">
              <label className="px-4 py-2.5 bg-stone-100 border border-stone-300 rounded-lg cursor-pointer hover:bg-stone-200 transition-colors text-sm font-medium inline-block">
                {audioUploading ? '上传中...' : '选择音频文件'}
                <input
                  type="file"
                  accept="audio/*"
                  onChange={handleAudioUpload}
                  className="hidden"
                  disabled={audioUploading}
                />
              </label>
              {audioFileName && (
                <span className="text-sm text-stone-600 truncate max-w-xs">
                  {audioFileName}
                  {audioUploading && ' (上传中...)'}
                </span>
              )}
              {form.audio_path && !audioUploading && (
                <span className="text-xs text-green-600">✓ 已上传（将存入数据库）</span>
              )}
            </div>
            {/* URL 直接输入（备用） */}
            <div>
              <label className="block text-xs text-stone-400 mb-1">
                或直接填写音频 URL（外部托管）
              </label>
              <input
                type="url"
                value={form.audio_url}
                onChange={(e) => {
                  handleChange('audio_url', e.target.value);
                  if (e.target.value) handleChange('audio_path', '');
                }}
                placeholder="https://example.com/episode.mp3"
                className="w-full px-4 py-2.5 border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent/50"
              />
            </div>
          </div>
          <p className="mt-1 text-xs text-stone-400">
            上传文件直接存入数据库；填写外部 URL 则使用远程托管
          </p>
        </div>
      </div>

      {/* Description */}
      <div>
        <label className="block text-sm font-medium mb-2">节目简介</label>
        <RichTextEditor
          content={form.description}
          onChange={(html) => handleChange('description', html)}
          placeholder="输入节目简介..."
        />
      </div>

      {/* Transcript */}
      <div>
        <label className="block text-sm font-medium mb-2">逐字稿</label>
        <RichTextEditor
          content={form.transcript}
          onChange={(html) => handleChange('transcript', html)}
          placeholder="输入逐字稿内容..."
        />
      </div>

      {/* Submit */}
      <div className="flex gap-4 pt-4">
        <button
          type="submit"
          disabled={saving}
          className="px-6 py-3 bg-accent text-white rounded-lg font-medium hover:bg-amber-700 transition-colors disabled:opacity-50"
        >
          {saving ? '保存中...' : episode ? '更新节目' : '创建节目'}
        </button>
        <button
          type="button"
          onClick={() => router.push('/admin')}
          className="px-6 py-3 border border-stone-300 rounded-lg font-medium hover:bg-stone-100 transition-colors"
        >
          取消
        </button>
      </div>
    </form>
  );
}
