import Link from 'next/link';
import type { Metadata } from 'next';
import { Episode, hasDbAudio } from '@/lib/types';
import db from '@/lib/db';
import PlayButton from '@/components/PlayButton';

const BASE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? 'https://dongtaipingheng.com';
const DESCRIPTION =
  '在变化中寻找平衡，在对话中发现可能。每期邀请一位嘉宾，聊聊他们如何在快速变化的世界中，找到属于自己的节奏与平衡。';

export const metadata: Metadata = {
  title: '动态平衡 — 播客',
  description: DESCRIPTION,
  openGraph: {
    title: '动态平衡 — 播客',
    description: DESCRIPTION,
    url: BASE_URL,
    type: 'website',
    locale: 'zh_CN',
    siteName: '动态平衡',
  },
  alternates: {
    canonical: BASE_URL,
  },
};

async function getEpisodes(): Promise<Episode[]> {
  try {
    const result = await db.execute('SELECT * FROM episodes ORDER BY id DESC');
    return result.rows as unknown as Episode[];
  } catch {
    return [];
  }
}

export const dynamic = 'force-dynamic';

export default async function HomePage() {
  const episodes = await getEpisodes();
  const latestEpisodes = episodes.slice(0, 3);

  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'PodcastSeries',
    name: '动态平衡',
    description: DESCRIPTION,
    url: BASE_URL,
    inLanguage: 'zh-CN',
    author: {
      '@type': 'Person',
      name: '李逸',
    },
    publisher: {
      '@type': 'Organization',
      name: '动态平衡播客',
      url: BASE_URL,
    },
    webFeed: `${BASE_URL}/rss`,
  };

  return (
    <div className="min-h-screen">
      {/* JSON-LD */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      {/* Header */}
      <header className="border-b border-stone-200">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-4 sm:py-6 flex items-center justify-between">
          <Link href="/" className="text-lg sm:text-xl font-bold tracking-tight">
            动态平衡
          </Link>
          <nav className="flex gap-4 sm:gap-6 text-sm text-muted">
            <Link href="/" className="text-foreground font-medium">
              首页
            </Link>
            <Link href="/episodes" className="hover:text-foreground transition-colors">
              节目
            </Link>
            <Link href="/about" className="hover:text-foreground transition-colors">
              关于
            </Link>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 py-12 sm:py-20">
        <h1 className="text-4xl md:text-5xl font-bold tracking-tight mb-6">
          动态平衡
        </h1>
        <p className="text-lg text-muted max-w-2xl leading-relaxed">
          在变化中寻找平衡，在对话中发现可能。每期邀请一位嘉宾，聊聊他们如何在快速变化的世界中，找到属于自己的节奏与平衡。
        </p>
      </section>

      {/* Latest Episodes */}
      {latestEpisodes.length > 0 && (
        <section className="max-w-5xl mx-auto px-4 sm:px-6 pb-16">
          <h2 className="text-2xl font-bold mb-8">最新节目</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {latestEpisodes.map((episode) => (
              <Link
                key={episode.id}
                href={`/episodes/${episode.id}`}
                className="group block"
              >
                <div className="aspect-square relative rounded-xl overflow-hidden bg-stone-100 mb-4">
                  {episode.cover_image ? (
                    <img
                      src={episode.cover_image}
                      alt={episode.title}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-4xl font-bold text-stone-300">
                      {episode.episode_number}
                    </div>
                  )}
                  {(episode.audio_url || hasDbAudio(episode)) && (
                    <PlayButton
                      episode={{
                        id: episode.id,
                        title: episode.title,
                        episodeNumber: episode.episode_number,
                        audioUrl: hasDbAudio(episode) ? `/api/audio/${episode.id}` : episode.audio_url!,
                      }}
                      variant="hero"
                    />
                  )}
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-muted">
                    {episode.episode_number} · {episode.publish_date} · {episode.duration}
                  </p>
                  <h3 className="font-semibold group-hover:text-accent transition-colors">
                    {episode.title}
                  </h3>
                  {episode.guest && (
                    <p className="text-sm text-muted">嘉宾：{episode.guest}</p>
                  )}
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* All Episodes */}
      {episodes.length > 0 && (
        <section className="max-w-5xl mx-auto px-4 sm:px-6 pb-20">
          <h2 className="text-2xl font-bold mb-8">全部节目</h2>
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
                  {episode.audio_url || hasDbAudio(episode) ? (
                    <PlayButton
                      episode={{
                        id: episode.id,
                        title: episode.title,
                        episodeNumber: episode.episode_number,
                        audioUrl: hasDbAudio(episode) ? `/api/audio/${episode.id}` : episode.audio_url!,
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
      )}

      {/* Empty State */}
      {episodes.length === 0 && (
        <section className="max-w-5xl mx-auto px-6 pb-20 text-center py-20">
          <p className="text-muted text-lg">暂无节目，敬请期待。</p>
        </section>
      )}

      {/* Subscribe */}
      <section className="border-t border-stone-200 bg-stone-50">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-10 sm:py-16 text-center">
          <h2 className="text-2xl font-bold mb-4">订阅收听</h2>
          <p className="text-muted mb-8">在你喜欢的平台订阅「动态平衡」</p>
          <div className="flex flex-wrap justify-center gap-4">
            <a
              href="https://podcasts.apple.com"
              target="_blank"
              rel="noopener noreferrer"
              className="px-6 py-3 rounded-full border border-stone-300 text-sm font-medium hover:border-accent hover:text-accent transition-colors"
            >
              苹果播客
            </a>
            <a
              href="https://www.xiaoyuzhoufm.com"
              target="_blank"
              rel="noopener noreferrer"
              className="px-6 py-3 rounded-full border border-stone-300 text-sm font-medium hover:border-accent hover:text-accent transition-colors"
            >
              小宇宙
            </a>
            <a
              href="https://open.spotify.com"
              target="_blank"
              rel="noopener noreferrer"
              className="px-6 py-3 rounded-full border border-stone-300 text-sm font-medium hover:border-accent hover:text-accent transition-colors"
            >
              Spotify
            </a>
            <a
              href="/rss"
              className="px-6 py-3 rounded-full border border-stone-300 text-sm font-medium hover:border-accent hover:text-accent transition-colors"
            >
              RSS
            </a>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-stone-200">
        <div className="max-w-5xl mx-auto px-6 py-8 text-center text-sm text-muted">
          <p>© 2026 动态平衡播客. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
