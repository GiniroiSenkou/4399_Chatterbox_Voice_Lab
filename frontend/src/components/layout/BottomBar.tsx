import type { RefObject } from "react";
import { AudioPlayer } from "@/components/player/AudioPlayer";
import { usePlayerStore } from "@/stores/player-store";

interface Props {
  containerRef: RefObject<HTMLDivElement>;
}

export function BottomBar({ containerRef }: Props) {
  const { currentAudioUrl, abMode, audioA, audioB } = usePlayerStore();
  const hasLoadedAudio = !!currentAudioUrl || (abMode && (!!audioA || !!audioB));

  if (!hasLoadedAudio) return null;

  return (
    <div
      ref={containerRef}
      className="shrink-0 h-28 glass"
      style={{ borderTop: "1px solid var(--border-subtle)" }}
    >
      <AudioPlayer />
    </div>
  );
}
