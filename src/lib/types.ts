export interface Episode {
  id: number;
  episode_number: string;
  title: string;
  guest: string | null;
  description: string | null;
  transcript: string | null;
  cover_image: string | null;
  duration: string | null;
  publish_date: string | null;
  link_xiaoyuzhou: string | null;
  link_apple_podcasts: string | null;
  audio_url: string | null;
  audio_data: number[] | null;
  created_at: string;
  updated_at: string;
}

/** 判断节目是否在数据库中有音频二进制数据 */
export function hasDbAudio(episode: Episode): boolean {
  return !!(episode.audio_data && episode.audio_data.length > 0);
}
