"use client";
// Seven days at a glance: per doctor per day, who is booked, how much is
// free, or why the doctor isn't in. Any day opens as its diary page.
import type { Schemas } from "@/lib/api/client";
import { clockTime } from "@/lib/dates";
import { cn } from "@/lib/utils";
import { visitInfo } from "@/lib/visit";
import { HATCH } from "./day-grid";

type Week = Schemas["Week"];
type WeekDay = Schemas["WeekDay"];

const SHOWN = 4; // names per cell before "+n more"

const dayName = (day: string) =>
  new Intl.DateTimeFormat("en-IN", { weekday: "short", timeZone: "UTC" }).format(new Date(`${day}T00:00:00Z`));
const dayDate = (day: string) =>
  new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", timeZone: "UTC" }).format(new Date(`${day}T00:00:00Z`));

/** What one doctor's day comes to: booked count, free count, or why not in. */
function cell(day: WeekDay, doctorId: number, today: string) {
  const state = day.doctors.find((d) => d.doctor_id === doctorId);
  const appts = day.appointments.filter((a) => a.doctor_id === doctorId);
  const free = state && day.day >= today ? state.free : 0;
  const away = state?.off ?? (state && !state.sits && !appts.length ? "Not in" : null);
  return { appts, free, away };
}

export function WeekView({ data, today, wide, onOpenDay }: {
  data: Week; today: string; wide: boolean; onOpenDay: (day: string) => void;
}) {
  if (!data.doctors.length) {
    return <p className="rounded-xl border bg-card px-6 py-12 text-center text-sm text-muted-foreground">No doctors are taking bookings. Add one in Clinic settings.</p>;
  }
  return wide ? <WeekTable data={data} today={today} onOpenDay={onOpenDay} /> : <WeekList data={data} today={today} onOpenDay={onOpenDay} />;
}

function WeekTable({ data, today, onOpenDay }: { data: Week; today: string; onOpenDay: (day: string) => void }) {
  return (
    <div className="overflow-x-auto rounded-xl border bg-card">
      <div className="grid min-w-[60rem]" style={{ gridTemplateColumns: `11rem repeat(7, minmax(0, 1fr))` }}>
        <div className="border-b" />
        {data.days.map((d) => {
          const booked = d.appointments.length;
          return (
            <button key={d.day} type="button" onClick={() => onOpenDay(d.day)}
              className={cn("border-b border-l px-3 py-2.5 text-left hover:bg-muted/60", d.day === today && "bg-accent/60")}>
              <p className={cn("text-xs font-medium text-muted-foreground", d.day === today && "text-accent-foreground")}>
                {dayName(d.day)}{d.day === today && " · Today"}
              </p>
              <p className="font-semibold">{dayDate(d.day)}</p>
              <p className="text-xs text-muted-foreground tabular-nums">{booked} booked</p>
            </button>
          );
        })}
        {data.doctors.map((doc) => (
          <DoctorRow key={doc.id} name={doc.name} id={doc.id} days={data.days} today={today} onOpenDay={onOpenDay} />
        ))}
      </div>
    </div>
  );
}

function DoctorRow({ name, id, days, today, onOpenDay }: {
  name: string; id: number; days: WeekDay[]; today: string; onOpenDay: (day: string) => void;
}) {
  return (
    <>
      <div className="border-b px-3 py-3 font-medium last:border-b-0">{name}</div>
      {days.map((d) => {
        const { appts, free, away } = cell(d, id, today);
        return (
          <button key={d.day} type="button" onClick={() => onOpenDay(d.day)}
            aria-label={`${name}, ${dayName(d.day)} ${dayDate(d.day)}: ${away ?? `${appts.length} booked, ${free} free`}`}
            className={cn("min-h-28 border-b border-l px-2.5 py-2 text-left align-top text-xs hover:bg-muted/60",
              away && cn("bg-muted/60", HATCH), d.day === today && !away && "bg-accent/25")}>
            {away && <p className="font-medium text-muted-foreground">{away}</p>}
            <ul className="space-y-0.5">
              {appts.slice(0, SHOWN).map((a) => {
                const visit = visitInfo(a.visit);
                return (
                  <li key={a.id} className="flex items-center gap-1 truncate">
                    <span className="shrink-0 text-muted-foreground tabular-nums">{clockTime(a.starts_at).replace(" ", "")}</span>
                    <span className="truncate font-medium">{a.patient_name}</span>
                    {visit && <visit.icon className="size-3 shrink-0 text-muted-foreground" aria-label={visit.label} />}
                  </li>
                );
              })}
            </ul>
            {appts.length > SHOWN && <p className="mt-0.5 text-muted-foreground">+{appts.length - SHOWN} more</p>}
            {free > 0 && <p className="mt-1 font-medium text-accent-foreground tabular-nums">{free} free</p>}
          </button>
        );
      })}
    </>
  );
}

function WeekList({ data, today, onOpenDay }: { data: Week; today: string; onOpenDay: (day: string) => void }) {
  return (
    <ol className="space-y-2">
      {data.days.map((d) => (
        <li key={d.day}>
          <button type="button" onClick={() => onOpenDay(d.day)}
            className={cn("w-full rounded-xl border bg-card px-4 py-3 text-left", d.day === today && "border-primary/50 bg-accent/30")}>
            <p className="flex items-baseline justify-between">
              <span className="font-semibold">{dayName(d.day)} {dayDate(d.day)}{d.day === today && <span className="text-accent-foreground"> · Today</span>}</span>
              <span className="text-sm text-muted-foreground tabular-nums">{d.appointments.length} booked</span>
            </p>
            <ul className="mt-1.5 space-y-0.5 text-sm">
              {data.doctors.map((doc) => {
                const { appts, free, away } = cell(d, doc.id, today);
                return (
                  <li key={doc.id} className="flex justify-between gap-3">
                    <span className="truncate">{doc.name}</span>
                    <span className="shrink-0 text-muted-foreground tabular-nums">
                      {away ?? `${appts.length} booked${free ? ` · ${free} free` : ""}`}
                    </span>
                  </li>
                );
              })}
            </ul>
          </button>
        </li>
      ))}
    </ol>
  );
}
