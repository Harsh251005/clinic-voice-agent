"use client";
import { Suspense } from "react";
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation";
import { AlertCircle } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/app/page-header";
import { AppointmentList } from "@/components/appointments/appointment-list";
import { DayControls } from "@/components/appointments/day-controls";
import { Stats } from "@/components/appointments/stats";
import { isDay, todayIn } from "@/lib/dates";
import { useClinic, useDay } from "@/lib/queries";

function Appointments() {
  const clinicId = Number(useParams<{ clinicId: string }>().clinicId);
  const clinic = useClinic(clinicId);
  const search = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  // Today in the clinic's timezone, not the browser's.
  const today = clinic.data ? todayIn(clinic.data.timezone) : null;
  const asked = search.get("day");
  const day = isDay(asked) ? asked : today;
  const showCancelled = search.get("cancelled") === "1";
  const data = useDay(clinicId, day ?? "", showCancelled);

  // The day and toggle live in the URL: back/forward and bookmarks work.
  const go = (next: { day?: string; cancelled?: boolean }) => {
    const params = new URLSearchParams(search);
    if (next.day) params.set("day", next.day);
    if (next.cancelled !== undefined) {
      if (next.cancelled) params.set("cancelled", "1");
      else params.delete("cancelled");
    }
    router.replace(`${pathname}?${params}`, { scroll: false });
  };

  return (
    <>
      <PageHeader title="Appointments" description="Bookings made on calls appear here as soon as they are confirmed." />
      {!day || !today ? (
        <Skeleton className="h-10 w-96 max-w-full" />
      ) : (
        <div className="space-y-6">
          <DayControls
            day={day} today={today} showCancelled={showCancelled}
            onDay={(d) => go({ day: d })} onShowCancelled={(c) => go({ cancelled: c })}
          />
          {data.isError ? (
            <Alert variant="destructive">
              <AlertCircle />
              <AlertDescription>Couldn&apos;t load appointments: {data.error.message}</AlertDescription>
            </Alert>
          ) : !data.data ? (
            <div className="space-y-4">
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-48 w-full" />
            </div>
          ) : (
            <>
              <Stats booked={data.data.booked} onCalls={data.data.booked_on_calls} week={data.data.next_7_days} />
              <AppointmentList clinicId={clinicId} day={data.data.day} appointments={data.data.appointments} />
            </>
          )}
        </div>
      )}
    </>
  );
}

export default function AppointmentsPage() {
  return (
    <Suspense>
      <Appointments />
    </Suspense>
  );
}
