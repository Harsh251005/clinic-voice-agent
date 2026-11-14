"use client";
// Admin > Try: try any clinic's receptionist without being its staff
// (Harsh, 2026-11-14). Pick a clinic and chat with her brain; nothing is
// spent on hearing or voice, and no worker is needed.
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AlertCircle, Building2 } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/app/page-header";
import { Empty } from "@/components/admin/bits";
import { TryChat } from "@/components/admin/try/chat";
import { ClinicPicker } from "@/components/admin/try/clinic-picker";
import { useAdminClinics } from "@/lib/admin";

export default function Page() {
  return <Suspense fallback={<Skeleton className="h-64" />}><TryPage /></Suspense>;
}

function TryPage() {
  const clinics = useAdminClinics();
  const fromLink = Number(useSearchParams().get("clinic")) || null; // "Try her" on a clinic's page
  const [picked, setPicked] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const list = clinics.data ?? [];
  const clinic = list.find((c) => c.id === (picked ?? fromLink)) ?? (list.length === 1 ? list[0] : undefined);

  return (
    <div className="space-y-6">
      <PageHeader title="Try the receptionist"
        description="Be the caller yourself, for any clinic, without signing in as its staff." />
      {clinics.isError ? (
        <Alert variant="destructive"><AlertCircle /><AlertDescription>{clinics.error.message}</AlertDescription></Alert>
      ) : !clinics.data ? (
        <Skeleton className="h-64" />
      ) : !list.length ? (
        <Empty icon={<Building2 className="size-5" />} title="No clinics yet">Add a clinic first, then try its receptionist here.</Empty>
      ) : (
        <>
          <ClinicPicker clinics={list} value={clinic?.id ?? null} onChange={setPicked} disabled={busy} />
          {/* A new clinic is a new chat: the key drops the old one's state. */}
          {clinic
            ? <TryChat key={clinic.id} clinicId={clinic.id} clinicName={clinic.name} onBusy={setBusy} />
            : <p className="text-sm text-muted-foreground">Pick the clinic whose receptionist you want to try.</p>}
        </>
      )}
    </div>
  );
}
