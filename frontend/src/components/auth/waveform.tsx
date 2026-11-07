// A voice waveform that never stops: it breathes quietly while nobody talks
// and swells while someone speaks (`level`, 0 to 1). Pure CSS, so it costs
// nothing; still for viewers who ask for less motion (motion-safe).
import type { CSSProperties } from "react";
import { cn } from "@/lib/utils";

const BARS = 36;
// Fixed, speech-like shape and offsets: same on server and browser (no hydration mismatch).
const shape = Array.from({ length: BARS }, (_, i) => 0.35 + 0.65 * Math.abs(Math.sin(i * 0.55) * Math.cos(i * 0.21)));
const offset = Array.from({ length: BARS }, (_, i) => ((i * 137) % 1000) - 1000);

export function Waveform({ level, tone, className }: { level: number; tone: "agent" | "caller"; className?: string }) {
  return (
    <div
      className={cn("flex h-16 items-center justify-between gap-1", className)}
      style={{ "--level": level } as CSSProperties}
    >
      {shape.map((h, i) => (
        <span
          key={i}
          className={cn(
            "h-full w-1 origin-center rounded-full transition-colors duration-500 motion-safe:animate-wave",
            tone === "agent" ? "bg-teal-300" : "bg-sky-300",
          )}
          style={{ "--bar": h, animationDelay: `${offset[i]}ms`, transform: "scaleY(calc(var(--bar) * 0.3))" } as CSSProperties}
        />
      ))}
    </div>
  );
}
