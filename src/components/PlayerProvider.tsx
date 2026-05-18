'use client';

import {
  createContext,
  useContext,
  useRef,
  useState,
  useCallback,
  useEffect,
} from 'react';

export interface PlayableEpisode {
  id: number;
  title: string;
  episodeNumber: string;
  audioUrl: string;
}

interface PlayerState {
  isPlaying: boolean;
  currentEpisode: PlayableEpisode | null;
  play: (episode: PlayableEpisode) => void;
  pause: () => void;
  toggle: () => void;
  stop: () => void;
  audioRef: React.RefObject<HTMLAudioElement>;
}

const PlayerContext = createContext<PlayerState | null>(null);

export function usePlayer() {
  const ctx = useContext(PlayerContext);
  if (!ctx) throw new Error('usePlayer must be used inside PlayerProvider');
  return ctx;
}

export default function PlayerProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentEpisode, setCurrentEpisode] = useState<PlayableEpisode | null>(null);

  // Sync isPlaying with actual audio state
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const onPlay = () => setIsPlaying(true);
    const onPause = () => setIsPlaying(false);
    const onEnded = () => setIsPlaying(false);
    audio.addEventListener('play', onPlay);
    audio.addEventListener('pause', onPause);
    audio.addEventListener('ended', onEnded);
    return () => {
      audio.removeEventListener('play', onPlay);
      audio.removeEventListener('pause', onPause);
      audio.removeEventListener('ended', onEnded);
    };
  }, []);

  const play = useCallback((episode: PlayableEpisode) => {
    const audio = audioRef.current;
    if (!audio) return;

    if (currentEpisode?.id === episode.id) {
      // Same episode — just resume
      audio.play();
    } else {
      // New episode
      audio.src = episode.audioUrl;
      audio.load();
      audio.play();
      setCurrentEpisode(episode);
    }
  }, [currentEpisode]);

  const pause = useCallback(() => {
    audioRef.current?.pause();
  }, []);

  const toggle = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    if (isPlaying) {
      audio.pause();
    } else {
      audio.play();
    }
  }, [isPlaying]);

  const stop = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.pause();
    audio.src = '';
    setCurrentEpisode(null);
    setIsPlaying(false);
  }, []);

  return (
    <PlayerContext.Provider value={{ isPlaying, currentEpisode, play, pause, toggle, stop, audioRef }}>
      {/* Hidden audio element — lives in the layout, never unmounts */}
      <audio ref={audioRef} preload="metadata" />
      {children}
    </PlayerContext.Provider>
  );
}
