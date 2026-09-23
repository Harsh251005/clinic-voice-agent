import { PhoneCall, TriangleAlert, UserRound } from "lucide-react";
import type { Schemas } from "@/lib/api/client";
import { doctorToday } from "@/lib/clinic-day";
import { clockTime, span12 } from "@/lib/dates";
import { formatPhone } from "@/lib/phone";
import { cn } from "@/lib/utils";

type Appointment = Schemas["Appointment"];

/** One doctor's day: their hours today and the patients booked, in order,
 *  with the one in the chair and the next one marked. */
export function DoctorDay({ clinic, doctor, day, now, appointments }: {
  clinic: Schemas["Clinic"]; doctor: Schemas["Doctor"]; day: string; now: string; appointments: Appointment[];
}) {
  const today = doctorToday(clinic, doctor, day);
  const rows = [...appointments].sort((a, b) => a.starts_at.localeCompare(b.starts_at));
  const nowIdx = rows.findIndex((a) => a.starts_at.slice(11, 16) <= now && now < a.ends_at.slice(11, 16));
  const nextIdx = rows.findIndex((a) => a.starts_at.slice(11, 16) > now);

  return (
    <article className="overflow-hidden rounded-xl border bg-card">
      <header className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b px-5 py-3.5">
        <div className="grid size-9 shrink-0 place-items-center rounded-full bg-accent text-sm font-semibold text-accent-foreground" aria-hidden>
          {initials(doctor.name)}
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="font-semibold">{doctor.name}</h3>
          {doctor.specialty && <p className="text-sm text-muted-foreground">{doctor.specialty}</p>}
        </div>
        <p className={cn("basis-full pl-13 text-sm font-medium sm:basis-auto sm:pl-0", today.kind === "in" ? "text-foreground" : "text-muted-foreground")}>
          {today.kind === "in" ? today.sittings.map((s) => span12(s.start, s.end)).join(", ")
            : today.kind === "leave" ? `On leave today${today.reason ? ` · ${today.reason}` : ""}`
            : "Not in today"}
        </p>
      </header>
      {rows.length === 0 ? (
        <p className="px-5 py-4 text-sm text-muted-foreground">
          {today.kind === "in" ? "No appointments yet. Free all day." : "No appointments."}
        </p>
      ) : (
        <ol className="divide-y">
          {rows.map((a, i) => {
            const past = a.ends_at.slice(11, 16) <= now;
            return (
              <li key={a.id} className={cn("flex items-start gap-4 px-5 py-3", i === nowIdx && "bg-accent/40", past && "text-muted-foreground")}>
                <p className={cn("w-[4.5rem] shrink-0 pt-0.5 text-sm font-semibold tabular-nums", past && "font-medium")}>{clockTime(a.starts_at)}</p>
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-2 font-medium">
                    {a.patient_name}
                    {i === nowIdx && <Tag className="bg-primary text-primary-foreground">Now</Tag>}
                    {i === nextIdx && <Tag className="bg-accent text-accent-foreground">Next</Tag>}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    <a href={`tel:${a.patient_phone}`} className="tabular-nums hover:text-foreground">{formatPhone(a.patient_phone)}</a>
                    {a.reason && <> · {a.reason}</>}
                  </p>
                  {a.problem && (
                    <p className="mt-1 flex items-center gap-1.5 text-sm text-warning-foreground">
                      <TriangleAlert className="size-4 shrink-0" aria-hidden /> {a.problem}
                    </p>
                  )}
                </div>
                <p className="hidden shrink-0 items-center gap-1 pt-0.5 text-xs text-muted-foreground sm:flex">
                  {a.source === "voice"
                    ? <><PhoneCall className="size-3.5" aria-hidden /> By receptionist</>
                    : <><UserRound className="size-3.5" aria-hidden /> By staff</>}
                </p>
              </li>
            );
          })}
        </ol>
      )}
    </article>
  );
}

function Tag({ className, children }: { className: string; children: React.ReactNode }) {
  return <span className={cn("rounded px-1.5 py-px text-[11px] font-semibold tracking-wide uppercase", className)}>{children}</span>;
}

function initials(name: string) {
  const words = name.replace(/^dr\.?\s+/i, "").split(/\s+/).filter(Boolean);
  return (words[0]?.[0] ?? "") + (words.length > 1 ? words.at(-1)![0] : "");
}
