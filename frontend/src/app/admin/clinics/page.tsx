"use client";
// Every clinic on the service: taking calls or paused, how busy, any errors.
import Link from "next/link";
import { AlertCircle, Building2, ChevronRight, Plus } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/app/page-header";
import { ActiveBadge, Empty } from "@/components/admin/bits";
import { useAdminClinics, when } from "@/lib/admin";
import type { Schemas } from "@/lib/api/client";

export default function ClinicsPage() {
  const clinics = useAdminClinics();
  return (
    <div className="space-y-5">
      <PageHeader title="Clinics" description="Add, pause or remove a clinic, and choose who on its team can sign in."
        actions={<Button asChild><Link href="/new-clinic"><Plus /> Add a clinic</Link></Button>} />
      {clinics.isError ? (
        <Alert variant="destructive"><AlertCircle /><AlertDescription>{clinics.error.message}</AlertDescription></Alert>
      ) : !clinics.data ? (
        <Skeleton className="h-40" />
      ) : !clinics.data.length ? (
        <Empty icon={<Building2 className="size-5" />} title="No clinics yet">Add the first clinic to give it a receptionist.</Empty>
      ) : (
        <ul className="divide-y overflow-hidden rounded-xl border bg-card">
          {clinics.data.map((c) => <Row key={c.id} c={c} />)}
        </ul>
      )}
    </div>
  );
}

function Row({ c }: { c: Schemas["AdminClinic"] }) {
  return (
    <li>
      <Link href={`/admin/clinics/${c.id}`} className="grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1 px-5 py-4 hover:bg-muted/60 sm:grid-cols-[1fr_9rem_7rem_8rem_1.25rem]">
        <div className="min-w-0">
          <p className="truncate font-medium">{c.name}</p>
          <p className="truncate text-xs text-muted-foreground">
            {c.doctors} {c.doctors === 1 ? "doctor" : "doctors"} · {c.members.length} on the team · /call/{c.slug}
          </p>
        </div>
        <span className="justify-self-end sm:justify-self-start"><ActiveBadge active={c.active} /></span>
        <p className="text-sm">
          <span className="font-semibold tabular-nums">{c.calls_7d}</span> <span className="text-muted-foreground">calls, 7 days</span>
          {c.calls_with_errors_7d > 0 && <span className="block text-xs text-destructive">{c.calls_with_errors_7d} with errors</span>}
        </p>
        <p className="text-right text-xs text-muted-foreground sm:text-left">{c.last_call_at ? `Last call ${when(c.last_call_at)}` : "No calls yet"}</p>
        <ChevronRight className="hidden size-4 text-muted-foreground sm:block" aria-hidden />
      </Link>
    </li>
  );
}
