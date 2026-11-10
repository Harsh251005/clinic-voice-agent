"use client";
// A time of day, picked the way staff say it: hour, minutes, am or pm.
// The browser's own time field follows the computer's settings and can show
// a 24-hour clock ("17:00") beside a dashboard that says "5 pm" everywhere
// else. The value in and out stays "HH:MM" on a 24-hour clock, as the API
// wants it; "" means not chosen yet.
import { cn } from "@/lib/utils";

const HOURS = [12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11];

/** "17:05" -> { hour: 5, minute: 5, pm: true }; null for "" or anything else. */
function parts(value: string) {
  const m = /^(\d{1,2}):(\d{2})/.exec(value);
  if (!m) return null;
  const h = Number(m[1]);
  return { hour: ((h + 11) % 12) + 1, minute: Number(m[2]), pm: h >= 12 };
}

function join(hour: number, minute: number, pm: boolean) {
  const h = (hour % 12) + (pm ? 12 : 0);
  return `${String(h).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

/** Morning or evening for an hour picked first: a clinic's 9, 10 and 11 are
 *  mornings, its 12 to 8 afternoons and evenings. */
const likelyPm = (hour: number) => hour === 12 || hour < 9;

export function TimeField({ id, label, value, onChange, minuteStep = 5, required, bare, className }: {
  id?: string;
  label: string; // what the three parts are read out as: "Time", "Monday session 1 from"
  value: string;
  onChange: (value: string) => void;
  minuteStep?: number;
  required?: boolean;
  bare?: boolean; // no border of its own: it sits inside a bordered row
  className?: string;
}) {
  const now = parts(value);
  const minutes = Array.from({ length: 60 / minuteStep }, (_, i) => i * minuteStep);
  if (now && !minutes.includes(now.minute)) minutes.push(now.minute); // a time off the grid still shows
  minutes.sort((a, b) => a - b);
  const part = "h-full cursor-pointer appearance-none rounded-md bg-transparent px-1 text-center tabular-nums outline-none hover:bg-muted focus-visible:bg-muted disabled:cursor-default";
  const option = "bg-popover text-popover-foreground";

  return (
    <div role="group" aria-label={label} data-slot="time-field" data-value={value}
      className={cn(
        "inline-flex h-8 items-center gap-0.5 rounded-lg px-1 text-base md:text-sm",
        !bare && "border border-input transition-colors focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50 dark:bg-input/30",
        className,
      )}>
      <select id={id} aria-label={`${label}: hour`} required={required} className={part} value={now ? now.hour : ""}
        onChange={(e) => {
          const hour = Number(e.target.value);
          onChange(join(hour, now?.minute ?? 0, now ? now.pm : likelyPm(hour)));
        }}>
        {!now && <option value="" className={option}>--</option>}
        {HOURS.map((h) => <option key={h} value={h} className={option}>{h}</option>)}
      </select>
      <span aria-hidden className="text-muted-foreground">:</span>
      <select aria-label={`${label}: minutes`} className={part} value={now ? now.minute : ""} disabled={!now}
        onChange={(e) => now && onChange(join(now.hour, Number(e.target.value), now.pm))}>
        {!now && <option value="" className={option}>--</option>}
        {minutes.map((m) => <option key={m} value={m} className={option}>{String(m).padStart(2, "0")}</option>)}
      </select>
      <select aria-label={`${label}: am or pm`} className={cn(part, "ml-0.5")} value={now ? (now.pm ? "pm" : "am") : ""} disabled={!now}
        onChange={(e) => now && onChange(join(now.hour, now.minute, e.target.value === "pm"))}>
        {!now && <option value="" className={option}>--</option>}
        <option value="am" className={option}>am</option>
        <option value="pm" className={option}>pm</option>
      </select>
    </div>
  );
}
