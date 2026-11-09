"use client";
// Plays one recording (WAV from the API). One plays at a time: starting
// another stops the first. `version` (when it was recorded) makes a new
// take of the same words load fresh instead of from the browser's cache.
import { useEffect, useState } from "react";
import { Pause, Play } from "lucide-react";
import { Button } from "@/components/ui/button";

let current: { audio: HTMLAudioElement; stop: () => void } | null = null;

export function PlayButton({ clipKey, version, label }: { clipKey: string; version: string; label: string }) {
  const [playing, setPlaying] = useState(false);
  const src = `/api/admin/voice/clips/${clipKey}.wav?v=${encodeURIComponent(version)}`;

  useEffect(() => () => {
    if (current?.audio.src.endsWith(src)) current.audio.pause();
  }, [src]);

  const toggle = () => {
    if (playing) {
      current?.audio.pause();
      return;
    }
    current?.audio.pause();
    const audio = new Audio(src);
    const stop = () => setPlaying(false);
    audio.addEventListener("play", () => setPlaying(true));
    audio.addEventListener("pause", stop);
    audio.addEventListener("ended", stop);
    current = { audio, stop };
    audio.play().catch(stop);
  };

  return (
    <Button variant="outline" size="sm" onClick={toggle} aria-label={`${playing ? "Stop" : "Play"} ${label}`} aria-pressed={playing}>
      {playing ? <Pause /> : <Play />} {playing ? "Stop" : "Play"}
    </Button>
  );
}
