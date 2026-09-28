"use client";
// The diary: a day as a grid of doctors and time (a list on phones), a week
// at a glance, and search by patient. View, day and search live in the URL,
// so back/forward and bookmarks work.
import { Suspense, useEffect, useState } from "react";
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation";
import { AlertCircle, Plus } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/app/page-header";
import { AppointmentDialog, type Slot } from "@/components/appointments/appointment-form";
import { DiaryControls, weekStart, type View } from "@/components/appointments/day-controls";
import { DayGrid } from "@/components/appointments/day-grid";
import { DayList } from "@/components/appointments/day-list";
import { SearchResults } from "@/components/appointments/search-results";
import { Stats } from "@/components/appointments/stats";
import { WeekView } from "@/components/appointments/week-view";
import type { Schemas } from "@/lib/api/client";
import { useClinicNow, useWide } from "@/lib/clinic-now";
import { isDay } from "@/lib/dates";
import { useAppointmentSearch, useClinic, useDay, useWeek } from "@/lib/queries";

const SEARCH_DELAY_MS = 300;

function Appointments() {
  const clinicId = Number(useParams<{ clinicId: string }>().clinicId);
  const clinic = useClinic(clinicId);
  const now = useClinicNow(clinic.data?.timezone);
  const wide = useWide();
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const today = now?.day ?? null;
  const asked = params.get("day");
  const day = isDay(asked) ? asked : today;
  const view: View = params.get("view") === "week" ? "week" : "day";
  const showCancelled = params.get("cancelled") === "1";
  const q = params.get("q") ?? "";

  const go = (next: { day?: string; view?: View; cancelled?: boolean; q?: string }) => {
    const p = new URLSearchParams(params);
    if (next.day) p.set("day", next.day);
    if (next.view) { if (next.view === "week") p.set("view", "week"); else p.delete("view"); }
    if (next.cancelled !== undefined) { if (next.cancelled) p.set("cancelled", "1"); else p.delete("cancelled"); }
    if (next.q !== undefined) { if (next.q.trim()) p.set("q", next.q); else p.delete("q"); }
    router.replace(`${pathname}?${p}`, { scroll: false });
  };

  // What's typed shows at once; the search (and the URL) follow a moment later.
  const [typed, setTyped] = useState(q);
  useEffect(() => {
    if (typed === q) return;
    const id = setTimeout(() => go({ q: typed }), SEARCH_DELAY_MS);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- go is rebuilt each render; typed is the trigger
  }, [typed]);

  const [booking, setBooking] = useState<Slot | "new" | null>(null);
  const openDay = (d: string) => { setTyped(""); go({ day: d, view: "day", q: "" }); };

  return (
    <>
      <PageHeader
        title="Appointments"
        description="Bookings from calls appear as soon as they are confirmed. Click a free time to book it, or a booking to mark the visit, change or cancel it."
        actions={<Button onClick={() => setBooking("new")} disabled={!clinic.data || !day}><Plus /> New appointment</Button>}
      />
      {clinic.data && day && (
        <AppointmentDialog clinic={clinic.data} day={day} at={booking && booking !== "new" ? booking : undefined}
          open={booking !== null} onOpenChange={(open) => !open && setBooking(null)} />
      )}
      {clinic.isError ? (
        <Failed what="your clinic" error={clinic.error} />
      ) : !day || !today || !now || !clinic.data ? (
        <Skeleton className="h-10 w-96 max-w-full" />
      ) : (
        <div className="space-y-6">
          <DiaryControls
            view={view} day={day} today={today} showCancelled={showCancelled} search={typed}
            onDay={(d) => go({ day: d })} onView={(v) => go({ view: v })}
            onShowCancelled={(c) => go({ cancelled: c })} onSearch={setTyped}
          />
          {q.trim().length >= 2 ? (
            <Search clinic={clinic.data} q={q} today={today} onOpenDay={openDay} />
          ) : view === "week" ? (
            <Week clinicId={clinicId} start={weekStart(day)} today={today} wide={wide} onOpenDay={openDay} />
          ) : (
            <DayView clinic={clinic.data} day={day} today={today} now={now.time} wide={wide}
              showCancelled={showCancelled} onBook={setBooking} />
          )}
        </div>
      )}
    </>
  );
}

function DayView({ clinic, day, today, now, wide, showCancelled, onBook }: {
  clinic: Schemas["Clinic"]; day: string; today: string; now: string; wide: boolean; showCancelled: boolean;
  onBook: (slot: Slot) => void;
}) {
  const data = useDay(clinic.id, day, showCancelled);
  if (data.isError) return <Failed what="appointments" error={data.error} />;
  if (!data.data) return <div className="space-y-4"><Skeleton className="h-24 w-full" /><Skeleton className="h-96 w-full" /></div>;
  return (
    <>
      <Stats day={data.data} />
      {wide
        ? <DayGrid clinic={clinic} data={data.data} today={today} now={now} onBook={onBook} />
        : <DayList key={day} clinic={clinic} data={data.data} today={today} onBook={onBook} />}
    </>
  );
}

function Week({ clinicId, start, today, wide, onOpenDay }: {
  clinicId: number; start: string; today: string; wide: boolean; onOpenDay: (day: string) => void;
}) {
  const data = useWeek(clinicId, start);
  if (data.isError) return <Failed what="the week" error={data.error} />;
  if (!data.data) return <Skeleton className="h-96 w-full" />;
  return <WeekView data={data.data} today={today} wide={wide} onOpenDay={onOpenDay} />;
}

function Search({ clinic, q, today, onOpenDay }: {
  clinic: Schemas["Clinic"]; q: string; today: string; onOpenDay: (day: string) => void;
}) {
  const data = useAppointmentSearch(clinic.id, q);
  if (data.isError) return <Failed what="search results" error={data.error} />;
  if (!data.data) return <Skeleton className="h-48 w-full" />;
  return <SearchResults clinic={clinic} q={q} results={data.data} today={today} onOpenDay={onOpenDay} />;
}

function Failed({ what, error }: { what: string; error: Error }) {
  return (
    <Alert variant="destructive">
      <AlertCircle />
      <AlertDescription>Couldn&apos;t load {what}: {error.message}</AlertDescription>
    </Alert>
  );
}

export default function AppointmentsPage() {
  return (
    <Suspense>
      <Appointments />
    </Suspense>
  );
}
