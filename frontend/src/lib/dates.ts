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
