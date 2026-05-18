'use client';

import Link from 'next/link';
import { useState, useEffect } from 'react';

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [authenticated, setAuthenticated] = useState(false);
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = sessionStorage.getItem('admin_token');
    if (token === 'authenticated') {
      setAuthenticated(true);
    }
    setLoading(false);
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    const res = await fetch('/api/auth', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    });

    if (res.ok) {
      sessionStorage.setItem('admin_token', 'authenticated');
      setAuthenticated(true);
    } else {
      setError('密码错误');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-muted">加载中...</p>
      </div>
    );
  }

  if (!authenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <form onSubmit={handleLogin} className="w-full max-w-sm space-y-4">
          <h1 className="text-2xl font-bold text-center">后台管理</h1>
          <p className="text-sm text-muted text-center">请输入管理密码</p>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="密码"
            className="w-full px-4 py-3 border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent/50"
            autoFocus
          />
          {error && <p className="text-red-500 text-sm">{error}</p>}
          <button
            type="submit"
            className="w-full px-4 py-3 bg-accent text-white rounded-lg font-medium hover:bg-amber-700 transition-colors"
          >
            登录
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-stone-50">
      <header className="bg-white border-b border-stone-200">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <Link href="/admin" className="text-lg font-bold">
              动态平衡 · 后台
            </Link>
            <nav className="flex gap-4 text-sm">
              <Link
                href="/admin"
                className="text-muted hover:text-foreground transition-colors"
              >
                节目管理
              </Link>
              <Link
                href="/admin/new"
                className="text-muted hover:text-foreground transition-colors"
              >
                新建节目
              </Link>
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <Link
              href="/"
              target="_blank"
              className="text-sm text-muted hover:text-foreground transition-colors"
            >
              查看网站 ↗
            </Link>
            <button
              onClick={() => {
                sessionStorage.removeItem('admin_token');
                setAuthenticated(false);
              }}
              className="text-sm text-muted hover:text-foreground transition-colors"
            >
              退出
            </button>
          </div>
        </div>
      </header>
      <main className="max-w-6xl mx-auto px-6 py-8">{children}</main>
    </div>
  );
}
