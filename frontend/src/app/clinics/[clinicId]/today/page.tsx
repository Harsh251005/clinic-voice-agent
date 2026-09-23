"use client";
// Today: the front desk's home. Who is in, who is next, what needs a call,
// and what the clinic still has to set up for its receptionist.
import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AlertCircle, CalendarPlus } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { AppointmentDialog } from "@/components/appointments/appointment-form";
import { Attention } from "@/components/today/attention";
import { DoctorDay } from "@/components/today/doctor-day";
import { OpenBadge } from "@/components/today/open-badge";
import { Receptionist } from "@/components/today/receptionist";
import { Summary } from "@/components/today/summary";
import { longDay, nowIn } from "@/lib/dates";
import { useClinic, useDay } from "@/lib/queries";

function greeting(time: string) {
  const hour = Number(time.slice(0, 2));
  return hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
}

/** The clinic's clock, ticking once a minute so "next" and "open" stay true. */
function useClinicNow(timezone: string | undefined) {
  const [now, setNow] = useState(() => (timezone ? nowIn(timezone) : null));
  useEffect(() => {
    if (!timezone) return;
    const tick = () => setNow(nowIn(timezone));
    tick();
    const id = setInterval(tick, 60_000);
    return () => clearInterval(id);
  }, [timezone]);
  return now;
}

export default function TodayPage() {
  const clinicId = Number(useParams<{ clinicId: string }>().clinicId);
  const clinic = useClinic(clinicId);
  const now = useClinicNow(clinic.data?.timezone);
  const day = useDay(clinicId, now?.day ?? "", false);
  const [adding, setAdding] = useState(false);

  if (clinic.isError) {
    return <Alert variant="destructive"><AlertCircle /><AlertDescription>Couldn&apos;t load your clinic: {clinic.error.message}</AlertDescription></Alert>;
  }
  if (!clinic.data || !now) return <TodaySkeleton />;

  const c = clinic.data;
  const appointments = (day.data?.appointments ?? []).filter((a) => a.status === "booked");
  const doctors = c.doctors.filter((d) => d.active);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-2">
          <p className="text-sm font-medium text-muted-foreground">{longDay(now.day)}</p>
          <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">{greeting(now.time)}</h1>
          <OpenBadge clinic={c} day={now.day} now={now.time} />
        </div>
        <Button size="lg" onClick={() => setAdding(true)}><CalendarPlus /> New appointment</Button>
        <AppointmentDialog clinic={c} day={now.day} open={adding} onOpenChange={setAdding} />
      </header>

      {day.isError ? (
        <Alert variant="destructive"><AlertCircle /><AlertDescription>Couldn&apos;t load today&apos;s appointments: {day.error.message}</AlertDescription></Alert>
      ) : !day.data ? (
        <Skeleton className="h-28 w-full rounded-xl" />
      ) : (
        <Summary appointments={appointments} week={day.data.next_7_days} now={now.time} />
      )}

      <div className="grid items-start gap-6 lg:grid-cols-[1fr_340px]">
        <section aria-labelledby="doctors-today" className="space-y-3">
          <div className="flex items-baseline justify-between">
            <h2 id="doctors-today" className="text-lg font-semibold">Doctors today</h2>
            <Link href={`/clinics/${clinicId}/appointments`} className="text-sm font-medium text-primary hover:underline">
              Open diary
            </Link>
          </div>
          {!doctors.length ? (
            <div className="rounded-xl border border-dashed bg-card p-8 text-center">
              <p className="font-medium">No doctors yet</p>
              <p className="mt-1 text-sm text-muted-foreground">Add your doctors and their hours so the receptionist can book them.</p>
              <Button asChild className="mt-4"><Link href={`/clinics/${clinicId}/setup?tab=doctors`}>Add a doctor</Link></Button>
            </div>
          ) : !day.data ? (
            <Skeleton className="h-48 w-full rounded-xl" />
          ) : (
            doctors.map((d) => (
              <DoctorDay key={d.id} clinic={c} doctor={d} day={now.day} now={now.time}
                appointments={appointments.filter((a) => a.doctor_id === d.id)} />
            ))
          )}
        </section>

        <aside className="space-y-6">
          {day.data && <Attention clinicId={clinicId} appointments={appointments} />}
          <Receptionist clinic={c} />
        </aside>
      </div>
    </div>
  );
}

function TodaySkeleton() {
  return (
    <div className="space-y-6" aria-busy>
      <div className="space-y-2"><Skeleton className="h-4 w-40" /><Skeleton className="h-9 w-64" /><Skeleton className="h-6 w-44" /></div>
      <Skeleton className="h-28 w-full rounded-xl" />
      <div className="grid gap-6 lg:grid-cols-[1fr_340px]"><Skeleton className="h-72 rounded-xl" /><Skeleton className="h-72 rounded-xl" /></div>
    </div>
  );
}
