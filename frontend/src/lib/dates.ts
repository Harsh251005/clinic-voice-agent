// Clinic times are naive and in the clinic's own timezone (the API sends
// "2026-12-07T10:00:00"); dates travel as "YYYY-MM-DD". These helpers never
// convert through the browser's timezone.

export function todayIn(timezone: string): string {
  // en-CA formats as YYYY-MM-DD.
  return new Intl.DateTimeFormat("en-CA", { timeZone: timezone }).format(new Date());
}

export function addDays(day: string, n: number): string {
  const d = new Date(`${day}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

export function isDay(value: string | null): value is string {
  return !!value && /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(value));
}

export function longDay(day: string): string {
  return new Intl.DateTimeFormat("en-IN", { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" })
    .format(new Date(`${day}T00:00:00Z`));
}

/** "10:30 am" from a naive "2026-12-07T10:30:00". */
export function clockTime(naive: string): string {
  const [h, m] = naive.slice(11, 16).split(":").map(Number);
  const suffix = h < 12 ? "am" : "pm";
  return `${((h + 11) % 12) + 1}:${String(m).padStart(2, "0")} ${suffix}`;
}

/** Date <-> "YYYY-MM-DD" for the calendar widget, without timezone drift. */
export function toDate(day: string): Date {
  const [y, m, d] = day.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function fromDate(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

/** "10 am", "5:30 pm" from "10:00", "17:30" or "17:30:00". Staff read
 *  12-hour times; 24-hour clocks stay internal. */
export function time12(hhmm: string): string {
  const [h, m] = hhmm.slice(0, 5).split(":").map(Number);
  const suffix = h < 12 ? "am" : "pm";
  const hour = ((h + 11) % 12) + 1;
  return m ? `${hour}:${String(m).padStart(2, "0")} ${suffix}` : `${hour} ${suffix}`;
}

/** "10 am–1 pm", or "5–8 pm" when both ends share am/pm. */
export function span12(start: string, end: string): string {
  const a = time12(start), b = time12(end);
  const [aNum, aSuffix] = a.split(" "), [, bSuffix] = b.split(" ");
  return aSuffix === bSuffix ? `${aNum}–${b}` : `${a}–${b}`;
}

/** The clinic's clock right now: its date, weekday (0 = Monday) and "HH:MM". */
export function nowIn(timezone: string): { day: string; weekday: number; time: string } {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-GB", {
      timeZone: timezone, year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", hourCycle: "h23",
    }).formatToParts(new Date()).map((p) => [p.type, p.value]),
  );
  const day = `${parts.year}-${parts.month}-${parts.day}`;
  return { day, weekday: weekdayOf(day), time: `${parts.hour}:${parts.minute}` };
}

/** 0 = Monday ... 6 = Sunday, as the API numbers weekdays. */
export function weekdayOf(day: string): number {
  return (new Date(`${day}T00:00:00Z`).getUTCDay() + 6) % 7;
}

const SHORT_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

type Sitting = { weekday: number; start: string; end: string };

/** A doctor's week as staff would say it: "Mon–Sat 10 am–1 pm, 5–8 pm · Sun closed". */
export function weekText(sittings: Sitting[]): string {
  if (!sittings.length) return "No hours set";
  const dayText = (d: number) =>
    sittings.filter((s) => s.weekday === d)
      .sort((a, b) => a.start.localeCompare(b.start))
      .map((s) => span12(s.start, s.end)).join(", ");
  const groups: { from: number; to: number; text: string }[] = [];
  for (let d = 0; d < 7; d++) {
    const text = dayText(d);
    const last = groups.at(-1);
    if (last && last.text === text) last.to = d;
    else groups.push({ from: d, to: d, text });
  }
  return groups
    .map(({ from, to, text }) => {
      const days = from === to ? SHORT_DAYS[from] : `${SHORT_DAYS[from]}–${SHORT_DAYS[to]}`;
      return `${days} ${text || "closed"}`;
    })
    .join(" · ");
}
