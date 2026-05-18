import Link from 'next/link';
import type { Metadata } from 'next';
import { Episode } from '@/lib/types';
import getDb from '@/lib/db';
import PlayButton from '@/components/PlayButton';

export const metadata: Metadata = {
  title: '全部节目',
  description: '动态平衡播客全部节目列表',
};

export const dynamic = 'force-dynamic';

export default function EpisodesPage() {
  const db = getDb();
  const episodes = db
    .prepare('SELECT * FROM episodes ORDER BY publish_date DESC, id DESC')
    .all() as Episode[];

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b border-stone-200">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-4 sm:py-6 flex items-center justify-between">
          <Link href="/" className="text-lg sm:text-xl font-bold tracking-tight">
            动态平衡
          </Link>
          <nav className="flex gap-4 sm:gap-6 text-sm text-muted">
            <Link href="/" className="hover:text-foreground transition-colors">
              首页
            </Link>
            <Link href="/episodes" className="text-foreground font-medium">
              节目
            </Link>
            <Link href="/about" className="hover:text-foreground transition-colors">
              关于
            </Link>
          </nav>
        </div>
      </header>

      {/* Page Title */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 pt-12 sm:pt-16 pb-8 sm:pb-10">
        <h1 className="text-3xl font-bold tracking-tight">全部节目</h1>
        <p className="text-muted mt-3">
          共 {episodes.length} 期
        </p>
      </section>

      {/* Episode List */}
      {episodes.length > 0 ? (
        <section className="max-w-5xl mx-auto px-4 sm:px-6 pb-20">
          <div className="space-y-0 divide-y divide-stone-200">
            {episodes.map((episode) => (
              <div
                key={episode.id}
                className="py-5 flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-6"
              >
                <span className="text-sm font-mono text-muted w-16 shrink-0">
                  {episode.episode_number}
                </span>
                <div className="flex-1 min-w-0">
                  <Link
                    href={`/episodes/${episode.id}`}
                    className="font-medium hover:text-accent transition-colors"
                  >
                    {episode.title}
                  </Link>
                  {episode.guest && (
                    <span className="text-sm text-muted ml-2">— {episode.guest}</span>
                  )}
                </div>
                <div className="flex items-center gap-3 sm:gap-4 text-sm text-muted shrink-0 flex-wrap">
                  <span className="hidden sm:inline">{episode.publish_date}</span>
                  <span>{episode.duration}</span>
                  {episode.audio_url ? (
                    <PlayButton
                      episode={{
                        id: episode.id,
                        title: episode.title,
                        episodeNumber: episode.episode_number,
                        audioUrl: episode.audio_url,
                      }}
                      variant="list"
                    />
                  ) : episode.link_xiaoyuzhou ? (
                    <a
                      href={episode.link_xiaoyuzhou}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:text-accent transition-colors"
                    >
                      收听
                    </a>
                  ) : null}
                  <Link
                    href={`/episodes/${episode.id}`}
                    className="hover:text-accent transition-colors"
                  >
                    逐字稿
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : (
        <section className="max-w-5xl mx-auto px-6 pb-20 text-center py-20">
          <p className="text-muted text-lg">暂无节目，敬请期待。</p>
        </section>
      )}

      {/* Footer */}
      <footer className="border-t border-stone-200">
        <div className="max-w-5xl mx-auto px-6 py-8 text-center text-sm text-muted">
          <p>© 2026 动态平衡播客. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
