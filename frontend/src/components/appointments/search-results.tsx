"use client";
// Finding a patient's appointments by name or number: upcoming first,
// then the most recent past ones, cancelled included.
import { CalendarDays, EllipsisVertical, SearchX } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Schemas } from "@/lib/api/client";
import { clockTime, longDay } from "@/lib/dates";
import { formatPhone } from "@/lib/phone";
import { cn } from "@/lib/utils";
import { AppointmentMenu } from "./actions";
import { StatusTag } from "./day-list";

const LIMIT = 50; // the API's cap

export function SearchResults({ clinic, q, results, today, onOpenDay }: {
  clinic: Schemas["Clinic"];
  q: string;
  results: Schemas["Appointment"][];
  today: string;
  onOpenDay: (day: string) => void;
}) {
  if (!results.length) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-xl border bg-card px-6 py-12 text-center">
        <SearchX className="size-8 text-muted-foreground" aria-hidden />
        <p className="font-medium">No appointments for &ldquo;{q.trim()}&rdquo;</p>
        <p className="text-sm text-muted-foreground">Search by part of the patient&apos;s name, or at least 3 digits of their mobile number.</p>
      </div>
    );
  }
  const upcoming = results.filter((a) => a.starts_at.slice(0, 10) >= today);
  const past = results.filter((a) => a.starts_at.slice(0, 10) < today);
  return (
    <div className="space-y-5">
      <p className="text-sm text-muted-foreground" role="status">
        {results.length === LIMIT ? `Showing the first ${LIMIT} matches. Type more to narrow it down.` : `${results.length} found`}
      </p>
      <Section title="Upcoming" rows={upcoming} clinic={clinic} today={today} onOpenDay={onOpenDay} />
      <Section title="Past" rows={past} clinic={clinic} today={today} onOpenDay={onOpenDay} />
    </div>
  );
}

function Section({ title, rows, clinic, today, onOpenDay }: {
  title: string;
  rows: Schemas["Appointment"][];
  clinic: Schemas["Clinic"];
  today: string;
  onOpenDay: (day: string) => void;
}) {
  if (!rows.length) return null;
  return (
    <section className="space-y-2">
      <h2 className="text-sm font-semibold text-muted-foreground">{title}</h2>
      <ul className="divide-y overflow-hidden rounded-xl border bg-card">
        {rows.map((a) => (
          <li key={a.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3">
            <div className="w-44 shrink-0">
              <p className="font-semibold tabular-nums">{clockTime(a.starts_at)}</p>
              <p className="text-sm text-muted-foreground">{longDay(a.starts_at.slice(0, 10))}</p>
            </div>
            <div className="min-w-40 flex-1">
              <p className={cn("font-medium", a.status === "cancelled" && "text-muted-foreground line-through")}>{a.patient_name}</p>
              <p className="text-sm text-muted-foreground tabular-nums">{formatPhone(a.patient_phone)} · {a.doctor_name}</p>
              <StatusTag appt={a} />
            </div>
            <div className="flex gap-1">
              <Button variant="ghost" size="sm" onClick={() => onOpenDay(a.starts_at.slice(0, 10))}>
                <CalendarDays /> Open day
              </Button>
              <AppointmentMenu clinic={clinic} appt={a} today={today}>
                <Button variant="ghost" size="icon" aria-label={`Actions for ${a.patient_name}'s appointment`}>
                  <EllipsisVertical />
                </Button>
              </AppointmentMenu>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
