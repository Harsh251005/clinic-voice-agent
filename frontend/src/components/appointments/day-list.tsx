"use client";
// The day on a phone: the grid doesn't fit, so one doctor at a time, as a
// list in time order with the free times between bookings as tap targets.
import { useState } from "react";
import { ChevronRight, PhoneCall, TriangleAlert } from "lucide-react";
import type { Schemas } from "@/lib/api/client";
import { clockTime, span12, time12 } from "@/lib/dates";
import { formatPhone } from "@/lib/phone";
import { cn } from "@/lib/utils";
import { visitInfo } from "@/lib/visit";
import { AppointmentMenu, statusWords } from "./actions";
import type { Slot } from "./appointment-form";

type Appointment = Schemas["Appointment"];

export function DayList({ clinic, data, today, onBook }: {
  clinic: Schemas["Clinic"];
  data: Schemas["Day"];
  today: string;
  onBook: (slot: Slot) => void;
}) {
  const [picked, setPicked] = useState<number | null>(null);
  if (!data.doctors.length) {
    return <p className="rounded-xl border bg-card px-4 py-10 text-center text-sm text-muted-foreground">No doctors are taking bookings. Add one in Clinic settings.</p>;
  }
  const doctor = data.doctors.find((d) => d.id === picked) ?? data.doctors[0];
  const appts = data.appointments.filter((a) => a.doctor_id === doctor.id).sort((a, b) => a.starts_at.localeCompare(b.starts_at));

  // Free times grouped between bookings, so a long free morning is one row of chips.
  const rows: ({ kind: "appt"; appt: Appointment } | { kind: "free"; times: string[] })[] = [];
  const free = doctor.free.map((t) => t.slice(0, 5));
  let f = 0;
  for (const appt of appts) {
    const times: string[] = [];
    while (f < free.length && free[f] < appt.starts_at.slice(11, 16)) times.push(free[f++]);
    if (times.length) rows.push({ kind: "free", times });
    rows.push({ kind: "appt", appt });
  }
  if (f < free.length) rows.push({ kind: "free", times: free.slice(f) });

  return (
    <div className="space-y-3">
      {data.doctors.length > 1 && (
        <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1" role="tablist" aria-label="Doctor">
          {data.doctors.map((d) => {
            const n = data.appointments.filter((a) => a.doctor_id === d.id && a.status === "booked").length;
            return (
              <button key={d.id} type="button" role="tab" aria-selected={d.id === doctor.id} onClick={() => setPicked(d.id)}
                className={cn("min-h-11 shrink-0 rounded-full border px-4 text-sm font-medium",
                  d.id === doctor.id ? "border-primary bg-primary text-primary-foreground" : "bg-card text-foreground")}>
                {d.name} <span className="opacity-75 tabular-nums">· {n}</span>
              </button>
            );
          })}
        </div>
      )}
      <section className="overflow-hidden rounded-xl border bg-card">
        <header className="border-b px-4 py-3">
          <h3 className="font-semibold">{doctor.name}</h3>
          <p className="text-sm text-muted-foreground">
            {!doctor.active ? "Not taking bookings" : doctor.off ?? (doctor.sittings.length
              ? doctor.sittings.map((s) => span12(s.start, s.end)).join(", ") : "Not in on this day")}
          </p>
        </header>
        {rows.length === 0 ? (
          <p className="px-4 py-6 text-sm text-muted-foreground">No appointments.</p>
        ) : (
          <ol className="divide-y">
            {rows.map((row) => row.kind === "free" ? (
              <li key={`free-${row.times[0]}`} className="px-4 py-3">
                <p className="mb-2 text-xs font-medium text-muted-foreground">Free: tap to book</p>
                <div className="flex flex-wrap gap-1.5">
                  {row.times.map((t) => (
                    <button key={t} type="button" onClick={() => onBook({ doctorId: doctor.id, time: t })}
                      aria-label={`Book ${doctor.name} at ${time12(t)}`}
                      className="min-h-9 rounded-md border border-dashed border-primary/40 px-2.5 text-sm text-accent-foreground tabular-nums hover:bg-accent">
                      + {time12(t)}
                    </button>
                  ))}
                </div>
              </li>
            ) : (
              <li key={row.appt.id}>
                <AppointmentMenu clinic={clinic} appt={row.appt} today={today}>
                  <button type="button" className="flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-muted/50"
                    aria-label={`${clockTime(row.appt.starts_at)}, ${row.appt.patient_name}, ${statusWords(row.appt).join(", ")}`}>
                    <span className="w-[4.5rem] shrink-0 pt-0.5 text-sm font-semibold tabular-nums">{clockTime(row.appt.starts_at)}</span>
                    <span className="min-w-0 flex-1">
                      <span className={cn("block font-medium", row.appt.status === "cancelled" && "text-muted-foreground line-through")}>
                        {row.appt.patient_name}
                      </span>
                      <span className="block text-sm text-muted-foreground tabular-nums">
                        {formatPhone(row.appt.patient_phone)}{row.appt.reason && ` · ${row.appt.reason}`}
                      </span>
                      {row.appt.problem && (
                        <span className="mt-1 flex items-center gap-1.5 text-sm text-warning-foreground">
                          <TriangleAlert className="size-4 shrink-0" aria-hidden /> Call the patient: {row.appt.problem}.
                        </span>
                      )}
                      <StatusTag appt={row.appt} />
                    </span>
                    <ChevronRight className="mt-1 size-4 shrink-0 text-muted-foreground" aria-hidden />
                  </button>
                </AppointmentMenu>
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}

export function StatusTag({ appt }: { appt: Appointment }) {
  const visit = visitInfo(appt.visit);
  const tag = "mt-1.5 inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium";
  if (appt.status === "cancelled") return <span className={cn(tag, "bg-muted text-muted-foreground")}>Cancelled</span>;
  if (visit) return <span className={cn(tag, visit.tone)}><visit.icon className="size-3.5" aria-hidden /> {visit.label}</span>;
  return appt.source === "voice"
    ? <span className={cn(tag, "bg-accent text-accent-foreground")}><PhoneCall className="size-3" aria-hidden /> By receptionist</span>
    : <span className={cn(tag, "bg-secondary text-secondary-foreground")}>By staff</span>;
}
