'use client';

import { usePlayer } from './PlayerProvider';
import PlayerProvider from './PlayerProvider';
import AudioPlayer from './AudioPlayer';

function PlayerShellInner({ children }: { children: React.ReactNode }) {
  const { currentEpisode } = usePlayer();
  return (
    <>
      {/* Add bottom padding only when player is visible */}
      <div style={{ paddingBottom: currentEpisode ? 72 : 0 }}>
        {children}
      </div>
      <AudioPlayer />
    </>
  );
}

export default function PlayerShell({ children }: { children: React.ReactNode }) {
  return (
    <PlayerProvider>
      <PlayerShellInner>{children}</PlayerShellInner>
    </PlayerProvider>
  );
}
