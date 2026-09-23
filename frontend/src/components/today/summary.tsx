import { PhoneCall } from "lucide-react";
import type { Schemas } from "@/lib/api/client";
import { clockTime } from "@/lib/dates";

type Appointment = Schemas["Appointment"];

/** One strip of the numbers the desk glances at, and who is next. */
export function Summary({ appointments, week, now }: { appointments: Appointment[]; week: number; now: string }) {
  const sorted = [...appointments].sort((a, b) => a.starts_at.localeCompare(b.starts_at));
  const next = sorted.find((a) => a.starts_at.slice(11, 16) > now);
  const inChair = sorted.filter((a) => a.starts_at.slice(11, 16) <= now && now < a.ends_at.slice(11, 16));
  const byReceptionist = appointments.filter((a) => a.source === "voice").length;
  const left = appointments.filter((a) => a.ends_at.slice(11, 16) > now).length;

  return (
    <div className="grid grid-cols-3 overflow-hidden rounded-xl border bg-card lg:grid-cols-[1.4fr_1fr_1fr_1fr]">
      <div className="col-span-3 border-b bg-accent/50 p-4 sm:p-5 lg:col-span-1 lg:border-r lg:border-b-0">
        <p className="text-sm font-medium text-accent-foreground">Next patient</p>
        {next ? (
          <>
            <p className="mt-1.5 text-xl font-semibold">{next.patient_name}</p>
            <p className="text-sm text-muted-foreground">
              <span className="font-medium text-foreground tabular-nums">{clockTime(next.starts_at)}</span> with {next.doctor_name}
            </p>
          </>
        ) : inChair.length ? (
          <p className="mt-1.5 text-muted-foreground">
            No one else today. With the doctor now: <span className="font-medium text-foreground">{inChair.map((a) => a.patient_name).join(", ")}</span>
          </p>
        ) : (
          <p className="mt-1.5 text-muted-foreground">No one else booked today.</p>
        )}
      </div>
      <Stat label="Appointments today" value={appointments.length} hint={`${left} left today`} />
      <Stat label="Booked by receptionist" value={byReceptionist} hint="from calls" icon={<PhoneCall className="size-4" aria-hidden />} />
      <Stat label="Next 7 days" value={week} hint="booked, from today" last />
    </div>
  );
}

function Stat({ label, value, hint, icon, last }: { label: string; value: number; hint: string; icon?: React.ReactNode; last?: boolean }) {
  return (
    <div className={`p-4 sm:p-5 ${last ? "" : "border-r"}`}>
      <p className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground sm:text-sm">
        <span className="hidden sm:inline">{icon}</span>{label}
      </p>
      <p className="mt-1 text-2xl font-semibold tabular-nums sm:text-3xl">{value}</p>
      <p className="text-xs text-muted-foreground">{hint}</p>
    </div>
  );
}
