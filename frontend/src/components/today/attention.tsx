import Link from "next/link";
import { CircleCheck, TriangleAlert } from "lucide-react";
import type { Schemas } from "@/lib/api/client";
import { clockTime } from "@/lib/dates";
import { formatPhone } from "@/lib/phone";

/** Bookings that can't go ahead as booked (leave, holiday, hours changed):
 *  someone should ring the patient. */
export function Attention({ clinicId, appointments }: { clinicId: number; appointments: Schemas["Appointment"][] }) {
  const flagged = appointments.filter((a) => a.problem);
  return (
    <section aria-labelledby="attention" className="rounded-xl border bg-card">
      <h2 id="attention" className="flex items-center gap-2 border-b px-5 py-3.5 font-semibold">
        Needs attention
        {flagged.length > 0 && (
          <span className="rounded-full bg-warning px-2 text-xs font-semibold text-warning-foreground tabular-nums">{flagged.length}</span>
        )}
      </h2>
      {flagged.length === 0 ? (
        <p className="flex items-center gap-2 px-5 py-4 text-sm text-muted-foreground">
          <CircleCheck className="size-4 text-success-foreground" aria-hidden /> Nothing today. All bookings can go ahead.
        </p>
      ) : (
        <ul className="divide-y">
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
