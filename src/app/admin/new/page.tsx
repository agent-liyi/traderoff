'use client';

import EpisodeForm from '@/components/EpisodeForm';

export default function NewEpisodePage() {
  return (
    <div>
      <h1 className="text-2xl font-bold mb-8">新建节目</h1>
      <EpisodeForm />
    </div>
  );
}
