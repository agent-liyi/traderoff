import Link from 'next/link';
import type { Metadata } from 'next';
import { Episode, hasDbAudio } from '@/lib/types';
import { notFound } from 'next/navigation';
import db from '@/lib/db';
import { htmlToExcerpt } from '@/lib/html-to-text';
import PlayButton from '@/components/PlayButton';

const BASE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? 'https://dongtaipingheng.com';

async function getEpisode(id: string): Promise<Episode | null> {
  try {
    const result = await db.execute({
      sql: 'SELECT * FROM episodes WHERE id = ?',
      args: [id],
    });
    if (result.rows.length === 0) return null;
    return result.rows[0] as unknown as Episode;
  } catch {
    return null;
  }
}

export const dynamic = 'force-dynamic';

/** ISO 8601 时长：将 "1:23:45" 或 "45:30" 转为 PT1H23M45S / PT45M30S */
function durationToISO(duration: string | null): string | null {
  if (!duration) return null;
  const parts = duration.split(':').map(Number);
  if (parts.some(isNaN)) return null;
  if (parts.length === 3) {
    const [h, m, s] = parts;
    return `PT${h}H${m}M${s}S`;
  }
  if (parts.length === 2) {
    const [m, s] = parts;
    return `PT${m}M${s}S`;
  }
  return null;
}

export async function generateMetadata({
  params,
}: {
  params: { id: string };
}): Promise<Metadata> {
  const episode = await getEpisode(params.id);
  if (!episode) return {};

  const description = episode.description
    ? htmlToExcerpt(episode.description, 150)
    : `「动态平衡」第 ${episode.episode_number} 期节目${episode.guest ? `，嘉宾：${episode.guest}` : ''}`;

  const title = episode.guest
    ? `${episode.title}（${episode.guest}）`
    : episode.title;

  const pageUrl = `${BASE_URL}/episodes/${episode.id}`;
  const imageUrl = episode.cover_image
    ? episode.cover_image.startsWith('http')
      ? episode.cover_image
      : `${BASE_URL}${episode.cover_image}`
    : undefined;

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      url: pageUrl,
      type: 'article',
      locale: 'zh_CN',
      siteName: '动态平衡',
      publishedTime: episode.publish_date ?? undefined,
      ...(imageUrl ? { images: [{ url: imageUrl, alt: episode.title }] } : {}),
    },
    alternates: {
      canonical: pageUrl,
    },
  };
}

export default async function EpisodePage({
  params,
}: {
  params: { id: string };
}) {
  const episode = await getEpisode(params.id);

  if (!episode) {
    notFound();
  }

  const pageUrl = `${BASE_URL}/episodes/${episode.id}`;
  const imageUrl = episode.cover_image
    ? episode.cover_image.startsWith('http')
      ? episode.cover_image
      : `${BASE_URL}${episode.cover_image}`
    : undefined;

  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'PodcastEpisode',
    name: episode.title,
    url: pageUrl,
    ...(episode.publish_date ? { datePublished: episode.publish_date } : {}),
    ...(durationToISO(episode.duration)
      ? { duration: durationToISO(episode.duration) }
      : {}),
    description: episode.description
      ? htmlToExcerpt(episode.description, 300)
      : undefined,
    ...(episode.description
      ? { articleBody: htmlToExcerpt(episode.description, 300) }
      : {}),
    ...(episode.transcript
      ? { transcript: htmlToExcerpt(episode.transcript, 500) }
      : {}),
    ...(imageUrl
      ? { image: { '@type': 'ImageObject', url: imageUrl } }
      : {}),
    author: {
      '@type': 'Person',
      name: '李逸',
    },
    ...(episode.guest
      ? {
          actor: {
            '@type': 'Person',
            name: episode.guest,
          },
        }
      : {}),
    partOfSeries: {
      '@type': 'PodcastSeries',
      name: '动态平衡',
      url: BASE_URL,
    },
    ...(episode.link_xiaoyuzhou || episode.link_apple_podcasts
      ? {
          associatedMedia: [
            ...(episode.link_xiaoyuzhou
              ? [
                  {
                    '@type': 'AudioObject',
                    contentUrl: episode.link_xiaoyuzhou,
                    name: `${episode.title} — 小宇宙`,
                  },
                ]
              : []),
            ...(episode.link_apple_podcasts
              ? [
                  {
                    '@type': 'AudioObject',
                    contentUrl: episode.link_apple_podcasts,
                    name: `${episode.title} — 苹果播客`,
                  },
                ]
              : []),
          ],
        }
      : {}),
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

      {/* Episode Content */}
      <article className="max-w-3xl mx-auto px-4 sm:px-6 py-8 sm:py-12">
        {/* Cover */}
        {episode.cover_image && (
          <div className="aspect-video relative rounded-xl overflow-hidden bg-stone-100 mb-8">
            <img
              src={episode.cover_image}
              alt={episode.title}
              className="w-full h-full object-cover"
            />
          </div>
        )}

        {/* Meta */}
        <header className="mb-8">
          <p className="text-sm text-muted mb-2">
            <span>{episode.episode_number}</span>
            {episode.publish_date && (
              <>
                {' · '}
                <time dateTime={episode.publish_date}>{episode.publish_date}</time>
              </>
            )}
            {episode.duration && <> · {episode.duration}</>}
          </p>
          <h1 className="text-3xl md:text-4xl font-bold mb-3">{episode.title}</h1>
          {episode.guest && (
            <p className="text-lg text-muted">
              嘉宾：<span itemProp="actor">{episode.guest}</span>
            </p>
          )}
        </header>

        {/* Links */}
        <div className="flex flex-wrap gap-3 mb-10">
          {(episode.audio_url || hasDbAudio(episode)) && (
            <PlayButton
              episode={{
                id: episode.id,
                title: episode.title,
                episodeNumber: episode.episode_number,
                audioUrl: hasDbAudio(episode) ? `/api/audio/${episode.id}` : episode.audio_url!,
              }}
              variant="detail"
            />
          )}
          {episode.link_xiaoyuzhou && (
            <a
              href={episode.link_xiaoyuzhou}
              target="_blank"
              rel="noopener noreferrer"
              className={`px-5 py-2.5 rounded-full text-sm font-medium transition-colors ${
                episode.audio_url
                  ? 'border border-stone-300 hover:border-accent hover:text-accent'
                  : 'bg-accent text-white hover:bg-amber-700'
              }`}
            >
              在小宇宙收听
            </a>
          )}
          {episode.link_apple_podcasts && (
            <a
              href={episode.link_apple_podcasts}
              target="_blank"
              rel="noopener noreferrer"
              className="px-5 py-2.5 border border-stone-300 rounded-full text-sm font-medium hover:border-accent hover:text-accent transition-colors"
            >
              在苹果播客收听
            </a>
          )}
        </div>

        {/* Description */}
        {episode.description && (
          <section aria-labelledby="description-heading" className="mb-12">
            <h2 id="description-heading" className="text-xl font-bold mb-4">节目简介</h2>
            <div
              className="prose text-foreground leading-relaxed"
              dangerouslySetInnerHTML={{ __html: episode.description }}
            />
          </section>
        )}

        {/* Transcript */}
        {episode.transcript && (
          <section id="transcript" aria-labelledby="transcript-heading" className="mb-12">
            <h2 id="transcript-heading" className="text-xl font-bold mb-4">逐字稿</h2>
            <div
              className="prose text-foreground leading-relaxed"
              dangerouslySetInnerHTML={{ __html: episode.transcript }}
            />
          </section>
        )}

        {/* Back */}
        <div className="pt-8 border-t border-stone-200">
          <Link
            href="/"
            className="text-sm text-muted hover:text-accent transition-colors"
          >
            ← 返回全部节目
          </Link>
        </div>
      </article>

      {/* Footer */}
      <footer className="border-t border-stone-200">
        <div className="max-w-5xl mx-auto px-6 py-8 text-center text-sm text-muted">
          <p>© 2026 动态平衡播客. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
