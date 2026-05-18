import { MetadataRoute } from 'next';
import getDb from '@/lib/db';
import { Episode } from '@/lib/types';

export const dynamic = 'force-dynamic';

const BASE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? 'https://dongtaipingheng.com';

export default function sitemap(): MetadataRoute.Sitemap {
  let episodes: Episode[] = [];
  try {
    const db = getDb();
    episodes = db
      .prepare('SELECT id, updated_at, publish_date FROM episodes ORDER BY id ASC')
      .all() as Episode[];
  } catch {
    episodes = [];
  }

  const staticPages: MetadataRoute.Sitemap = [
    {
      url: BASE_URL,
      lastModified: new Date(),
      changeFrequency: 'weekly',
      priority: 1.0,
    },
    {
      url: `${BASE_URL}/episodes`,
      lastModified: new Date(),
      changeFrequency: 'weekly',
      priority: 0.9,
    },
    {
      url: `${BASE_URL}/about`,
      lastModified: new Date('2026-01-01'),
      changeFrequency: 'monthly',
      priority: 0.5,
    },
  ];

  const episodePages: MetadataRoute.Sitemap = episodes.map((ep) => ({
    url: `${BASE_URL}/episodes/${ep.id}`,
    lastModified: ep.updated_at ? new Date(ep.updated_at) : new Date(),
    changeFrequency: 'monthly' as const,
    priority: 0.8,
  }));

  return [...staticPages, ...episodePages];
}
