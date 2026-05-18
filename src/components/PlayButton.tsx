'use client';

import { usePlayer, PlayableEpisode } from './PlayerProvider';

interface PlayButtonProps {
  episode: PlayableEpisode;
  variant?: 'list' | 'hero' | 'detail';
  className?: string;
}

export default function PlayButton({ episode, variant = 'list', className }: PlayButtonProps) {
  const { isPlaying, currentEpisode, play, pause } = usePlayer();

  const isThisEpisode = currentEpisode?.id === episode.id;
  const isThisPlaying = isThisEpisode && isPlaying;

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (isThisPlaying) {
      pause();
    } else {
      play(episode);
    }
  };

  if (variant === 'detail') {
    return (
      <button
        onClick={handleClick}
        className={`inline-flex items-center gap-2 px-5 py-2.5 bg-accent text-white rounded-full text-sm font-medium hover:bg-amber-700 transition-colors ${className ?? ''}`}
      >
        {isThisPlaying ? (
          <>
            <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
              <rect x="3" y="2" width="4" height="12" rx="1" />
              <rect x="9" y="2" width="4" height="12" rx="1" />
            </svg>
            暂停
          </>
        ) : (
          <>
            <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
              <path d="M4 2.5l9 5.5-9 5.5V2.5z" />
            </svg>
            {isThisEpisode ? '继续播放' : '站内播放'}
          </>
        )}
      </button>
    );
  }

  if (variant === 'hero') {
    // Overlay play button on cover image
    return (
      <button
        onClick={handleClick}
        aria-label={isThisPlaying ? '暂停' : '播放'}
        className={`absolute inset-0 flex items-center justify-center bg-black/0 group-hover:bg-black/20 transition-colors ${className ?? ''}`}
      >
        <span className="w-12 h-12 rounded-full bg-white/90 flex items-center justify-center shadow opacity-0 group-hover:opacity-100 transition-opacity">
          {isThisPlaying ? (
            <svg width="18" height="18" viewBox="0 0 16 16" fill="#b45309">
              <rect x="3" y="2" width="4" height="12" rx="1" />
              <rect x="9" y="2" width="4" height="12" rx="1" />
            </svg>
          ) : (
            <svg width="18" height="18" viewBox="0 0 16 16" fill="#b45309">
              <path d="M5 2.5l8 5.5-8 5.5V2.5z" />
            </svg>
          )}
        </span>
        {/* Always-visible indicator when this episode is actively playing */}
        {isThisPlaying && (
          <span className="absolute bottom-2 right-2 flex items-end gap-px h-3" aria-hidden>
            <span className="w-0.5 bg-white rounded-sm animate-eq1" style={{ height: '60%' }} />
            <span className="w-0.5 bg-white rounded-sm animate-eq2" style={{ height: '100%' }} />
            <span className="w-0.5 bg-white rounded-sm animate-eq3" style={{ height: '40%' }} />
          </span>
        )}
      </button>
    );
  }

  // variant === 'list'
  return (
    <button
      onClick={handleClick}
      className={`inline-flex items-center gap-1 hover:text-accent transition-colors ${className ?? ''}`}
    >
      {isThisPlaying ? (
        <>
          <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
            <rect x="3" y="2" width="4" height="12" rx="1" />
            <rect x="9" y="2" width="4" height="12" rx="1" />
          </svg>
          暂停
        </>
      ) : (
        <>
          <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
            <path d="M4 2.5l9 5.5-9 5.5V2.5z" />
          </svg>
          收听
        </>
      )}
    </button>
  );
}
