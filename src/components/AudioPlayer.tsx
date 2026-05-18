'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { usePlayer } from './PlayerProvider';

function formatTime(seconds: number): string {
  if (isNaN(seconds) || seconds < 0) return '0:00';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) {
    return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  }
  return `${m}:${String(s).padStart(2, '0')}`;
}

export default function AudioPlayer() {
  const { isPlaying, currentEpisode, toggle, stop, audioRef } = usePlayer();

  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [dragValue, setDragValue] = useState(0);
  const progressRef = useRef<HTMLInputElement>(null);

  // Sync time display
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const onTimeUpdate = () => {
      if (!isDragging) setCurrentTime(audio.currentTime);
    };
    const onDurationChange = () => setDuration(audio.duration || 0);
    const onWaiting = () => setIsLoading(true);
    const onCanPlay = () => setIsLoading(false);
    const onPlaying = () => setIsLoading(false);
    const onLoadStart = () => {
      setIsLoading(true);
      setCurrentTime(0);
      setDuration(0);
    };

    audio.addEventListener('timeupdate', onTimeUpdate);
    audio.addEventListener('durationchange', onDurationChange);
    audio.addEventListener('waiting', onWaiting);
    audio.addEventListener('canplay', onCanPlay);
    audio.addEventListener('playing', onPlaying);
    audio.addEventListener('loadstart', onLoadStart);

    return () => {
      audio.removeEventListener('timeupdate', onTimeUpdate);
      audio.removeEventListener('durationchange', onDurationChange);
      audio.removeEventListener('waiting', onWaiting);
      audio.removeEventListener('canplay', onCanPlay);
      audio.removeEventListener('playing', onPlaying);
      audio.removeEventListener('loadstart', onLoadStart);
    };
  }, [audioRef, isDragging]);

  const handleSeekStart = () => {
    setIsDragging(true);
    setDragValue(currentTime);
  };

  const handleSeekChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setDragValue(Number(e.target.value));
  };

  const handleSeekEnd = () => {
    const newTime = dragValue ?? currentTime;
    setIsDragging(false);
    setCurrentTime(newTime);
    if (audioRef.current) {
      audioRef.current.currentTime = newTime;
    }
  };

  const displayTime = isDragging ? dragValue : currentTime;
  const progress = duration > 0 ? (displayTime / duration) * 100 : 0;

  if (!currentEpisode) return null;

  return (
    <div
      className="fixed bottom-0 left-0 right-0 z-50 bg-white border-t border-stone-200 shadow-lg"
      style={{ animation: 'slideUp 0.25s ease-out' }}
    >
      <div className="max-w-5xl mx-auto px-4 h-[72px] flex items-center gap-3 sm:gap-5">
        {/* Play / Pause / Loading button */}
        <button
          onClick={toggle}
          aria-label={isPlaying ? '暂停' : '播放'}
          className="shrink-0 w-10 h-10 flex items-center justify-center rounded-full bg-accent text-white hover:bg-amber-700 transition-colors"
        >
          {isLoading ? (
            <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
          ) : isPlaying ? (
            // Pause icon
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <rect x="3" y="2" width="4" height="12" rx="1" />
              <rect x="9" y="2" width="4" height="12" rx="1" />
            </svg>
          ) : (
            // Play icon
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <path d="M4 2.5l9 5.5-9 5.5V2.5z" />
            </svg>
          )}
        </button>

        {/* Episode info + progress */}
        <div className="flex-1 min-w-0 flex flex-col justify-center gap-1">
          {/* Title */}
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-xs font-mono text-stone-400 shrink-0">
              {currentEpisode.episodeNumber}
            </span>
            <span className="text-sm font-medium truncate text-stone-800">
              {currentEpisode.title}
            </span>
            {/* Equalizer animation when playing */}
            {isPlaying && !isLoading && (
              <span className="shrink-0 flex items-end gap-px h-3.5" aria-hidden>
                <span className="w-0.5 bg-accent rounded-sm animate-eq1" style={{ height: '60%' }} />
                <span className="w-0.5 bg-accent rounded-sm animate-eq2" style={{ height: '100%' }} />
                <span className="w-0.5 bg-accent rounded-sm animate-eq3" style={{ height: '40%' }} />
                <span className="w-0.5 bg-accent rounded-sm animate-eq1" style={{ height: '80%' }} />
              </span>
            )}
          </div>

          {/* Progress bar + times */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-stone-400 shrink-0 tabular-nums w-10 text-right hidden sm:inline">
              {formatTime(displayTime)}
            </span>
            <input
              ref={progressRef}
              type="range"
              min={0}
              max={duration || 100}
              step={0.5}
              value={displayTime}
              onMouseDown={handleSeekStart}
              onTouchStart={handleSeekStart}
              onChange={handleSeekChange}
              onMouseUp={handleSeekEnd}
              onTouchEnd={handleSeekEnd}
              className="flex-1 h-1.5 appearance-none bg-stone-200 rounded-full cursor-pointer accent-amber-700"
              aria-label="播放进度"
            />
            <span className="text-xs text-stone-400 shrink-0 tabular-nums w-10 hidden sm:inline">
              {formatTime(duration)}
            </span>
          </div>
        </div>

        {/* Close button */}
        <button
          onClick={stop}
          aria-label="关闭播放器"
          className="shrink-0 w-8 h-8 flex items-center justify-center rounded-full text-stone-400 hover:text-stone-600 hover:bg-stone-100 transition-colors"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M2 2l10 10M12 2L2 12" />
          </svg>
        </button>
      </div>
    </div>
  );
}
