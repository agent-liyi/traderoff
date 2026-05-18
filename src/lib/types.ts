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
  created_at: string;
  updated_at: string;
}
