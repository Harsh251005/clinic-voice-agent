"use client";
// Small pieces the admin pages share: a call's result as icon + word, a
// stat tile, a day-range picker, an empty state.
import type { ReactNode } from "react";
import { CalendarCheck, CalendarX, CircleDot, CirclePause, CirclePlay, CircleHelp, MicOff, Repeat, TriangleAlert, Unplug } from "lucide-react";
import { cn } from "@/lib/utils";
import { OUTCOMES, type CallSummary } from "@/lib/admin";

const TONES = {
  good: "bg-success text-success-foreground",
  bad: "bg-destructive/10 text-destructive",
  warn: "bg-warning text-warning-foreground",
  plain: "bg-muted text-muted-foreground",
  live: "bg-accent text-accent-foreground",
} as const;

/** What happened on a call, never colour alone. */
export function CallResult({ call }: { call: Pick<CallSummary, "status" | "outcome"> }) {
  const [tone, Icon, word] =
    call.status === "live" ? (["live", CircleDot, "Live now"] as const)
    : call.status === "dropped" ? (["bad", Unplug, "Dropped"] as const)
    : call.outcome === "booked" ? (["good", CalendarCheck, OUTCOMES.booked] as const)
    : call.outcome === "moved" ? (["good", Repeat, OUTCOMES.moved] as const)
    : call.outcome === "cancelled" ? (["plain", CalendarX, OUTCOMES.cancelled] as const)
    : call.outcome === "failed" ? (["bad", TriangleAlert, OUTCOMES.failed] as const)
    : call.outcome === "no_action" ? (["plain", MicOff, OUTCOMES.no_action] as const)
    : (["plain", CircleHelp, OUTCOMES[call.outcome] ?? call.outcome] as const);
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap", TONES[tone])}>
      <Icon className="size-3.5" aria-hidden /> {word}
    </span>
  );
}

export function Stat({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: ReactNode; tone?: "bad" }) {
  return (
    <div className="p-4 sm:p-5">
      <p className="text-xs font-medium text-muted-foreground sm:text-sm">{label}</p>
      <p className={cn("mt-1 text-2xl font-semibold tabular-nums sm:text-3xl", tone === "bad" && "text-destructive")}>{value}</p>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

export function DaysPicker({ value, onChange }: { value: number; onChange: (days: number) => void }) {
  return (
    <div role="radiogroup" aria-label="Period" className="inline-flex rounded-lg border bg-card p-0.5">
      {[1, 7, 30].map((d) => (
        <button key={d} type="button" role="radio" aria-checked={value === d} onClick={() => onChange(d)}
          className={cn("rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors",
            value === d && "bg-foreground text-background")}>
          {d === 1 ? "24 hours" : `${d} days`}
        </button>
      ))}
    </div>
  );
}

export function Empty({ icon, title, children }: { icon: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed bg-card px-6 py-12 text-center">
      <span className="mx-auto mb-3 grid size-10 place-items-center rounded-lg bg-muted text-muted-foreground">{icon}</span>
      <p className="font-medium">{title}</p>
      {children && <p className="mx-auto mt-1 max-w-sm text-sm text-muted-foreground">{children}</p>}
    </div>
  );
}

/** Whether a clinic's receptionist is answering. */
export function ActiveBadge({ active }: { active: boolean }) {
  return active ? (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-success px-2.5 py-0.5 text-xs font-medium text-success-foreground">
      <CirclePlay className="size-3.5" aria-hidden /> Taking calls
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-warning px-2.5 py-0.5 text-xs font-medium text-warning-foreground">
      <CirclePause className="size-3.5" aria-hidden /> Paused
    </span>
  );
}
