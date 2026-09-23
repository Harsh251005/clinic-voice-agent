import type { Schemas } from "@/lib/api/client";
import { openState } from "@/lib/clinic-day";
import { time12 } from "@/lib/dates";
import { cn } from "@/lib/utils";

/** "Open now · until 1 pm", "Closed · opens at 5 pm", "Closed today · Diwali". */
export function OpenBadge({ clinic, day, now }: { clinic: Schemas["Clinic"]; day: string; now: string }) {
  const state = openState(clinic, day, now);
  const [open, text] =
    state.kind === "open" ? [true, `Open now · until ${time12(state.until)}`]
    : state.kind === "opens" ? [false, `Closed now · opens at ${time12(state.at)}`]
    : state.kind === "closed-today" ? [false, `Closed today${state.reason ? ` · ${state.reason}` : ""}`]
    : [false, "Closed for the day"];
  return (
    <p className={cn(
      "inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-medium",
      open ? "bg-success text-success-foreground" : "bg-muted text-muted-foreground",
    )}>
      <span className={cn("size-2 rounded-full", open ? "animate-pulse bg-success-foreground" : "bg-muted-foreground/60")} aria-hidden />
      {text}
    </p>
  );
}
