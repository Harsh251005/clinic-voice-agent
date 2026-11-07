"use client";
// The signature of the sign-in page: an example Hindi call playing on a loop
// (waveform, the words as they are said, the booking at the end), so a clinic
// sees what ClinicDesk does before signing in. Decorative: hidden from screen
// readers, labelled "Example" for everyone else.
import { useEffect, useState } from "react";
import { CalendarCheck } from "lucide-react";
import { cn } from "@/lib/utils";
import { BOOKED, CALL } from "./call-script";
import { useCallLoop } from "./use-call-loop";
import { Waveform } from "./waveform";

const enter = "motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-2 animation-duration-300 fill-mode-both";

function CallTimer({ cycle, reduced }: { cycle: number; reduced: boolean }) {
  const [seconds, setSeconds] = useState(0);
  const [seen, setSeen] = useState(cycle);
  if (seen !== cycle) { setSeen(cycle); setSeconds(0); } // a new call starts at 0:00
  useEffect(() => {
    if (reduced) return;
    const t = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [reduced]);
  return <span className="font-mono text-xs tabular-nums text-white/50">{`${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`}</span>;
}

export function LiveCall({ className }: { className?: string }) {
  const { shown, speaking, booked, leaving, cycle, reduced } = useCallLoop();
  const lastSpeaker = speaking ?? CALL[Math.max(0, shown - 1)].who;
  const ending = booked || leaving;

  return (
    <div aria-hidden className={cn("relative", className)}>
      {/* The glow under the panel follows whoever is talking. */}
      <div className={cn(
        "absolute -inset-6 -z-10 rounded-[2rem] blur-2xl transition-colors duration-700",
        lastSpeaker === "agent" ? "bg-teal-400/15" : "bg-sky-400/12",
      )} />
      <div className="overflow-hidden rounded-2xl border border-white/10 bg-white/[0.04] shadow-2xl backdrop-blur-xl">
        <div className="flex items-center justify-between border-b border-white/10 px-5 py-3">
          <div className="flex items-center gap-2.5">
            <span className="relative flex size-2">
              <span className="absolute inline-flex size-full rounded-full bg-emerald-400 opacity-60 motion-safe:animate-ping" />
              <span className="relative inline-flex size-2 rounded-full bg-emerald-400" />
            </span>
            <span className="text-sm font-medium text-white/90">Patient call</span>
            <span className="rounded-full border border-white/15 px-2 py-0.5 text-[10px] font-medium tracking-wider text-white/50 uppercase">Example</span>
          </div>
          <CallTimer cycle={cycle} reduced={reduced} />
        </div>

        <div className="px-5 pt-5">
          <Waveform level={speaking ? (speaking === "agent" ? 1 : 0.7) : 0.12} tone={lastSpeaker} />
          <p className="mt-2 text-center text-[11px] font-medium tracking-wider text-white/40 uppercase">
            {speaking === "agent" ? "Receptionist speaking" : speaking === "caller" ? "Patient speaking" : ending ? "Call ended" : "Listening"}
          </p>
        </div>

        <div className={cn(
          // Older lines slide up and fade out under the top edge, like a chat scrolling.
          "flex h-[17.5rem] flex-col justify-end gap-3 overflow-hidden px-5 pt-4 pb-5 transition-opacity duration-700 ease-in-out [mask-image:linear-gradient(to_bottom,transparent,black_18%)]",
          leaving && "opacity-0",
        )}>
          {CALL.slice(0, shown).map((line, i) => (
            <div key={`${cycle}-${i}`} className={cn("flex shrink-0", line.who === "caller" && "justify-end", enter)}>
              <p className={cn(
                "max-w-[85%] rounded-2xl px-4 py-2.5 text-[15px] leading-relaxed",
                line.who === "agent"
                  ? "rounded-bl-md bg-teal-400/15 text-teal-50 ring-1 ring-teal-300/20"
                  : "rounded-br-md bg-white/[0.07] text-white/85",
              )}>
                {line.text}
              </p>
            </div>
          ))}
                    {booked && (
            <div key={`booked-${cycle}`} className={cn("flex shrink-0 items-center gap-3 rounded-xl bg-emerald-400/10 px-4 py-3 ring-1 ring-emerald-300/25", enter)}>
              <span className="grid size-8 place-items-center rounded-lg bg-emerald-400/20 text-emerald-300">
                <CalendarCheck className="size-4" />
              </span>
              <div>
                <p className="text-sm font-medium text-emerald-100">{BOOKED.title}</p>
                <p className="text-xs text-emerald-200/60">{BOOKED.detail}</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
