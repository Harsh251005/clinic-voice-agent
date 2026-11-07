// A small drawing of the Today screen for the brand panel. Made-up rows,
// labelled "Example", so nobody mistakes it for a real clinic's patients.
// It rises in last, then its rows arrive one by one, like a day filling up.
import { rise, slideIn } from "./motion";

const ROW_DELAYS = ["[--tw-animation-delay:900ms]", "[--tw-animation-delay:1050ms]", "[--tw-animation-delay:1200ms]"];
const ROWS = [
  { time: "10:00 AM", who: "Patient A", what: "Check-up", by: "Booked on a call" },
  { time: "10:30 AM", who: "Patient B", what: "Follow-up", by: "Moved on a call" },
  { time: "11:15 AM", who: "Patient C", what: "Consultation", by: "Added by staff" },
];

export function TodayPreview() {
  return (
    <div aria-hidden className={`${rise} [--tw-animation-delay:650ms] max-w-md rounded-xl bg-sidebar-accent/70 p-4 shadow-2xl ring-1 ring-sidebar-border backdrop-blur-sm`}>
      <div className="mb-3 flex items-center justify-between">
        <p className="text-sm font-semibold text-sidebar-accent-foreground">Today</p>
        <span className="rounded-full bg-sidebar-border px-2 py-0.5 text-[11px] tracking-wide uppercase">Example</span>
      </div>
      <ul className="space-y-2">
        {ROWS.map((r, i) => (
          <li key={r.time} className={`${slideIn} ${ROW_DELAYS[i]} flex items-center gap-3 rounded-lg bg-sidebar/60 px-3 py-2 text-sm`}>
            <span className="w-16 shrink-0 font-mono text-xs tabular-nums">{r.time}</span>
            <span className="min-w-0 flex-1 truncate">
              <span className="font-medium text-sidebar-accent-foreground">{r.who}</span> · {r.what}
            </span>
            <span className="shrink-0 rounded-md bg-sidebar-primary/15 px-2 py-0.5 text-[11px] font-medium text-sidebar-primary">{r.by}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
