'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import EpisodeForm from '@/components/EpisodeForm';
import { Episode } from '@/lib/types';

export default function EditEpisodePage() {
  const params = useParams();
  const [episode, setEpisode] = useState<Episode | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchEpisode = async () => {
      const res = await fetch(`/api/episodes/${params.id}`);
      if (res.ok) {
        const data = await res.json();
        setEpisode(data);
      }
      setLoading(false);
    };
    fetchEpisode();
  }, [params.id]);

  if (loading) {
    return <p className="text-muted">加载中...</p>;
  }

  if (!episode) {
    return <p className="text-red-500">节目不存在</p>;
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-8">编辑节目</h1>
      <EpisodeForm episode={episode} />
    </div>
  );
}
