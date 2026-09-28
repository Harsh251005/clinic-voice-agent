"use client";
// The day as a diary page: a column per doctor, time running down. Working
// hours are white, the rest shaded; leave and holidays say why. Free slots
// are drawn and clickable, so booking into a gap is one click.
import { useEffect, useRef } from "react";
import { PhoneCall, TriangleAlert } from "lucide-react";
import type { Schemas } from "@/lib/api/client";
import { clockTime, span12, time12 } from "@/lib/dates";
import { cn } from "@/lib/utils";
import { visitInfo, VISITS } from "@/lib/visit";
import { AppointmentMenu, statusWords } from "./actions";
import type { Slot } from "./appointment-form";

type Day = Schemas["Day"];
type Appointment = Schemas["Appointment"];
type DoctorDay = Schemas["DoctorDay"];

/** "10:15" or "10:15:00" → minutes after midnight. */
const minutes = (hhmm: string) => Number(hhmm.slice(0, 2)) * 60 + Number(hhmm.slice(3, 5));
const hhmm = (m: number) => `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
const startOf = (a: Appointment) => minutes(a.starts_at.slice(11, 16));
// A booking past midnight (typed by staff) is drawn to the end of the day.
const endOf = (a: Appointment) => (a.ends_at.slice(0, 10) > a.starts_at.slice(0, 10) ? 24 * 60 : minutes(a.ends_at.slice(11, 16)));

export const HATCH = "bg-[repeating-linear-gradient(135deg,var(--color-border)_0_1px,transparent_1px_9px)]";

type Item =
  | { kind: "appt"; appt: Appointment; start: number; end: number }
  | { kind: "free"; time: string; start: number; end: number };
type Placed = Item & { lane: number; lanes: number };

/** Side by side where items overlap (a cancelled booking under a new one,
 *  an old overlap from changed hours); full width everywhere else. */
function place(items: Item[]): Placed[] {
  const sorted = [...items].sort((a, b) => a.start - b.start || a.end - b.end);
  const out: Placed[] = [];
  let cluster: Placed[] = [], laneEnds: number[] = [], clusterEnd = -1;
  const close = () => { for (const p of cluster) p.lanes = laneEnds.length; out.push(...cluster); };
  for (const item of sorted) {
    if (item.start >= clusterEnd && cluster.length) { close(); cluster = []; laneEnds = []; }
    let lane = laneEnds.findIndex((end) => end <= item.start);
    if (lane === -1) lane = laneEnds.push(item.end) - 1;
    else laneEnds[lane] = item.end;
    cluster.push({ ...item, lane, lanes: 1 });
    clusterEnd = Math.max(clusterEnd, item.end);
  }
  if (cluster.length) close();
  return out;
}

export function DayGrid({ clinic, data, today, now, onBook }: {
  clinic: Schemas["Clinic"];
  data: Day;
  today: string; // the clinic's date
  now: string; // the clinic's clock, "HH:MM"
  onBook: (slot: Slot) => void;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const isToday = data.day === today;
  const nowMin = minutes(now);

  // The hours worth drawing: every sitting and every booking, whole hours.
  const edges = [
    ...data.doctors.flatMap((d) => d.sittings.flatMap((s) => [minutes(s.start), minutes(s.end)])),
    ...data.appointments.flatMap((a) => [startOf(a), endOf(a)]),
  ];
  const from = edges.length ? Math.floor(Math.min(...edges) / 60) * 60 : 0;
  const to = edges.length ? Math.min(24 * 60, Math.ceil(Math.max(...edges) / 60) * 60) : 0;
  // Tall enough that the shortest slot fits a line of text, never absurdly tall.
  const shortest = Math.min(...data.doctors.map((d) => d.slot_minutes), 30);
  const px = Math.min(3.6, Math.max(1.2, 36 / shortest));
  const top = (m: number) => (m - from) * px;

  // Open on the part of the day that matters: the last hour and what's next,
  // else the first booking or sitting.
  const firstBooking = data.appointments.length ? Math.min(...data.appointments.map(startOf)) : null;
  const focus = isToday && nowMin >= from && nowMin <= to ? nowMin : firstBooking ?? from;
  // Once per day shown: the clock ticking or a refresh must not yank the
  // view back while someone is scrolling.
  const scrolledFor = useRef<string | null>(null);
  useEffect(() => {
    if (scrolledFor.current === data.day || !scroller.current) return;
    scrolledFor.current = data.day;
    scroller.current.scrollTo({ top: Math.max(0, (focus - from - (focus === nowMin ? 60 : 15)) * px) });
  }, [data.day, focus, from, px, nowMin]);

  if (!data.doctors.length) {
    return <Empty>No doctors are taking bookings. Add one in Clinic settings.</Empty>;
  }
  if (!edges.length) {
    const off = data.doctors.find((d) => d.off)?.off;
    return <Empty>{off && data.doctors.every((d) => d.off) ? off : "No doctor sits on this day, and nothing is booked."}</Empty>;
  }

  const hours: number[] = [];
  for (let m = from; m < to; m += 60) hours.push(m);
  const height = (to - from) * px;
  const specialty = new Map(clinic.doctors.map((d) => [d.id, d.specialty]));

  return (
    <div className="space-y-3">
      <div ref={scroller} className="max-h-[70vh] overflow-auto rounded-xl border bg-card" role="region" aria-label="Day diary" tabIndex={0}>
        <div className="grid min-w-fit" style={{ gridTemplateColumns: `4.25rem repeat(${data.doctors.length}, minmax(13rem, 1fr))` }}>
          <div className="sticky top-0 left-0 z-30 border-b bg-card" />
          {data.doctors.map((d) => (
            <ColumnHead key={d.id} doctor={d} specialty={specialty.get(d.id) ?? ""}
              booked={data.appointments.filter((a) => a.doctor_id === d.id && a.status === "booked").length} />
          ))}

          <div className="sticky left-0 z-20 border-r bg-card" style={{ height }}>
            {hours.map((m) => (
              <span key={m} className="absolute right-2 -translate-y-1/2 text-xs text-muted-foreground tabular-nums first:translate-y-1" style={{ top: top(m) }}>
                {time12(hhmm(m))}
              </span>
            ))}
          </div>
          {data.doctors.map((d) => (
            <Column key={d.id} clinic={clinic} doctor={d} today={today} height={height} hours={hours}
              appointments={data.appointments.filter((a) => a.doctor_id === d.id)}
              top={top} px={px} nowTop={isToday && nowMin >= from && nowMin <= to ? top(nowMin) : null}
              onBook={(time) => onBook({ doctorId: d.id, time })} />
          ))}
        </div>
      </div>
      <Legend />
    </div>
  );
}

function ColumnHead({ doctor, specialty, booked }: { doctor: DoctorDay; specialty: string; booked: number }) {
  return (
    <div className="sticky top-0 z-20 border-b border-l bg-card px-3 py-2.5">
      <p className="flex items-baseline justify-between gap-2">
        <span className="truncate font-semibold">{doctor.name}</span>
        <span className="shrink-0 text-xs text-muted-foreground tabular-nums">{booked} booked</span>
      </p>
      <p className="truncate text-xs text-muted-foreground">
        {!doctor.active ? "Not taking bookings"
          : doctor.off ? doctor.off
          : doctor.sittings.length ? doctor.sittings.map((s) => span12(s.start, s.end)).join(", ")
          : "Not in on this day"}
        {specialty && doctor.active && !doctor.off && doctor.sittings.length ? ` · ${specialty}` : ""}
      </p>
    </div>
  );
}

function Column({ clinic, doctor, today, appointments, height, hours, top, px, nowTop, onBook }: {
  clinic: Schemas["Clinic"]; doctor: DoctorDay; today: string; appointments: Appointment[];
  height: number; hours: number[]; top: (m: number) => number; px: number; nowTop: number | null;
  onBook: (time: string) => void;
}) {
  const items = place([
    ...appointments.map((appt): Item => ({ kind: "appt", appt, start: startOf(appt), end: Math.max(endOf(appt), startOf(appt) + 5) })),
    ...doctor.free.map((t): Item => ({ kind: "free", time: t.slice(0, 5), start: minutes(t), end: minutes(t) + doctor.slot_minutes })),
  ]);
  return (
    <div className={cn("relative border-l bg-muted/60", HATCH)} style={{ height }}>
      {!doctor.off && doctor.sittings.map((s) => (
        <div key={s.start} className="absolute inset-x-0 bg-card" style={{ top: top(minutes(s.start)), height: (minutes(s.end) - minutes(s.start)) * px }} />
      ))}
      {hours.map((m) => (
        <div key={m} className="pointer-events-none absolute inset-x-0 border-t border-border" style={{ top: top(m) }}>
          <div className="absolute inset-x-0 border-t border-dashed border-border/60" style={{ top: 30 * px }} />
        </div>
      ))}
      {doctor.off && (
        <p className="absolute inset-x-3 top-3 rounded-md bg-card/90 px-2 py-1 text-center text-sm font-medium text-muted-foreground">{doctor.off}</p>
      )}
      {items.map((item) => {
        const style = {
          top: top(item.start) + 1,
          height: Math.max((item.end - item.start) * px - 2, 18),
          left: `calc(${(item.lane / item.lanes) * 100}% + 4px)`,
          width: `calc(${100 / item.lanes}% - 8px)`,
        };
        return item.kind === "free" ? (
          <button key={`free-${item.time}`} type="button" style={style} onClick={() => onBook(item.time)}
            aria-label={`Book ${doctor.name} at ${time12(item.time)}`}
            className="absolute z-10 flex items-center rounded-md border border-dashed border-primary/25 px-2 text-left text-xs text-muted-foreground/80 transition-colors hover:border-primary hover:bg-accent hover:text-accent-foreground focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
            <span className="truncate tabular-nums">+ {time12(item.time)}</span>
          </button>
        ) : (
          <AppointmentMenu key={item.appt.id} clinic={clinic} appt={item.appt} today={today}>
            <button type="button" style={style} className={cn("absolute z-10 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none", blockTone(item.appt))}
              aria-label={`${clockTime(item.appt.starts_at)}, ${item.appt.patient_name}, ${statusWords(item.appt).join(", ")}${item.appt.problem ? `. Call the patient: ${item.appt.problem}` : ""}`}>
              <Block appt={item.appt} tall={style.height >= 44} />
            </button>
          </AppointmentMenu>
        );
      })}
      {nowTop !== null && (
        // Under the blocks, not over them: a booking's time stays readable.
        <div className="pointer-events-none absolute inset-x-0 z-[5] border-t-2 border-destructive" style={{ top: nowTop }} aria-hidden>
          <span className="absolute -top-[5px] -left-[5px] size-2 rounded-full bg-destructive" />
        </div>
      )}
    </div>
  );
}

function blockTone(appt: Appointment) {
  const base = "overflow-hidden rounded-md px-2 py-1 text-left text-xs shadow-xs transition-[filter] hover:brightness-95";
  if (appt.status === "cancelled") return cn(base, "border border-dashed bg-muted text-muted-foreground shadow-none");
  const visit = visitInfo(appt.visit);
  return cn(
    base,
    visit ? visit.tone : "border-l-[3px] border-primary bg-accent text-accent-foreground",
    appt.problem && "ring-2 ring-warning-foreground/50",
  );
}

function Block({ appt, tall }: { appt: Appointment; tall: boolean }) {
  const visit = visitInfo(appt.visit);
  const cancelled = appt.status === "cancelled";
  return (
    <span className="flex h-full min-w-0 flex-col">
      <span className="flex min-w-0 items-center gap-1.5">
        <span className="shrink-0 font-semibold tabular-nums">{clockTime(appt.starts_at)}</span>
        <span className={cn("truncate font-medium", cancelled && "line-through")}>{appt.patient_name}</span>
        <span className="ml-auto flex shrink-0 items-center gap-1">
          {appt.problem && <TriangleAlert className="size-3.5" aria-hidden />}
          {appt.source === "voice" && <PhoneCall className="size-3" aria-hidden />}
          {visit && <visit.icon className="size-3.5" aria-hidden />}
        </span>
      </span>
      {tall && (
        <span className="truncate opacity-80">
          {cancelled ? "Cancelled" : visit ? visit.label : appt.reason || (appt.source === "voice" ? "By receptionist" : "By staff")}
        </span>
      )}
    </span>
  );
}

function Legend() {
  const chip = "inline-block size-3 rounded-sm";
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-muted-foreground" aria-label="Key">
      <li className="flex items-center gap-1.5"><span className={cn(chip, "border-l-[3px] border-primary bg-accent")} /> Booked</li>
      {VISITS.map((v) => (
        <li key={v.value} className="flex items-center gap-1.5"><v.icon className="size-3.5" aria-hidden /> {v.label}</li>
      ))}
      <li className="flex items-center gap-1.5"><PhoneCall className="size-3" aria-hidden /> By receptionist</li>
      <li className="flex items-center gap-1.5"><TriangleAlert className="size-3.5" aria-hidden /> Call the patient</li>
      <li className="flex items-center gap-1.5"><span className={cn(chip, "border border-dashed border-primary/40")} /> Free: click to book</li>
      <li className="flex items-center gap-1.5"><span className={cn(chip, "border bg-muted", HATCH)} /> Not working</li>
    </ul>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <div className="rounded-xl border bg-card px-6 py-12 text-center text-sm text-muted-foreground">{children}</div>;
}
