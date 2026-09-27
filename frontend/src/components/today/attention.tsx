import Link from "next/link";
import { CircleCheck, PhoneOff, TriangleAlert } from "lucide-react";
import type { Schemas } from "@/lib/api/client";
import { when } from "@/lib/admin";
import { clockTime } from "@/lib/dates";
import { formatPhone } from "@/lib/phone";

/** Bookings that can't go ahead as booked (leave, holiday, hours changed),
 *  and today's callers who may not have been helped (cut off, or something
 *  went wrong): someone should ring the patient. */
export function Attention({ clinicId, appointments, calls = [] }: {
  clinicId: number; appointments: Schemas["Appointment"][]; calls?: Schemas["ClinicCall"][];
}) {
  const flagged = appointments.filter((a) => a.problem);
  const count = flagged.length + calls.length;
  return (
    <section aria-labelledby="attention" className="rounded-xl border bg-card">
      <h2 id="attention" className="flex items-center gap-2 border-b px-5 py-3.5 font-semibold">
        Needs attention
        {count > 0 && (
          <span className="rounded-full bg-warning px-2 text-xs font-semibold text-warning-foreground tabular-nums">{count}</span>
        )}
      </h2>
      {count === 0 ? (
        <p className="flex items-center gap-2 px-5 py-4 text-sm text-muted-foreground">
          <CircleCheck className="size-4 text-success-foreground" aria-hidden /> Nothing today. All bookings can go ahead.
        </p>
      ) : (
        <ul className="divide-y">
          {calls.map((c) => (
            <li key={`call${c.id}`} className="space-y-1 px-5 py-3.5 text-sm">
              <p className="font-medium">A caller may not have been helped · <span className="tabular-nums">{when(c.started_at)}</span></p>
              <p className="flex items-start gap-1.5 text-warning-foreground">
                <PhoneOff className="mt-0.5 size-4 shrink-0" aria-hidden />
                {c.status === "dropped" ? "The call was cut off." : "Something went wrong on the call."}
              </p>
              <p className="text-muted-foreground">
                <Link className="font-medium text-primary hover:underline" href={`/clinics/${clinicId}/calls/${c.id}`}>Read the call</Link> to
                see who it was and ring them back.
              </p>
            </li>
          ))}
          {flagged.map((a) => (
            <li key={a.id} className="space-y-1 px-5 py-3.5 text-sm">
              <p className="font-medium">{a.patient_name} · <span className="tabular-nums">{clockTime(a.starts_at)}</span></p>
              <p className="flex items-start gap-1.5 text-warning-foreground">
                <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden /> {a.problem}
              </p>
              <p className="text-muted-foreground">
                Call <a className="font-medium text-foreground hover:underline" href={`tel:${a.patient_phone}`}>{formatPhone(a.patient_phone)}</a> to
                move or cancel it in the <Link className="font-medium text-primary hover:underline" href={`/clinics/${clinicId}/appointments`}>diary</Link>.
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
