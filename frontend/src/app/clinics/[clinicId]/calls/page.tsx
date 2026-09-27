"use client";
// The clinic's calls, newest first: when, what happened, how long. Opens to
// what was said.
import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AlertCircle, ChevronRight, PhoneOff } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/app/page-header";
import { CallResult, Empty } from "@/components/admin/bits";
import { duration, when } from "@/lib/admin";
import { changeText, visitTime, whatHappened } from "@/lib/calls";
import { useClinicCalls } from "@/lib/queries";
import { cn } from "@/lib/utils";

const PAGE = 50; // the API's page size

export default function CallsPage() {
  const clinicId = Number(useParams<{ clinicId: string }>().clinicId);
  const [cursors, setCursors] = useState<(number | undefined)[]>([undefined]);
  return (
    <div className="space-y-5">
      <PageHeader title="Calls" description="Every call your receptionist took. Open one to read what was said." />
      <div className="overflow-hidden rounded-xl border bg-card">
        <div className="hidden grid-cols-[9rem_9rem_1fr_5rem_1.25rem] gap-4 border-b bg-muted/50 px-5 py-2.5 text-xs font-medium text-muted-foreground md:grid">
          <span>When</span><span>Result</span><span>What happened</span><span>Length</span><span />
        </div>
        {cursors.map((cursor, i) => (
          <CallRows key={cursor ?? "first"} clinicId={clinicId} beforeId={cursor} first={i === 0}
            onMore={i === cursors.length - 1 ? (last) => setCursors([...cursors, last]) : undefined} />
        ))}
      </div>
    </div>
  );
}

function CallRows({ clinicId, beforeId, first, onMore }: {
  clinicId: number; beforeId?: number; first: boolean; onMore?: (lastId: number) => void;
}) {
  const calls = useClinicCalls(clinicId, beforeId);
  if (calls.isError) return <Alert variant="destructive" className="m-3 w-auto"><AlertCircle /><AlertDescription>{calls.error.message}</AlertDescription></Alert>;
  if (!calls.data) return <div className="space-y-2 p-4">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-10" />)}</div>;
  if (first && !calls.data.length) {
    return (
      <div className="p-4">
        <Empty icon={<PhoneOff className="size-5" />} title="No calls yet">
          Calls appear here as soon as they start. Try one from the Today page.
        </Empty>
      </div>
    );
  }
  const rows = calls.data;
  return (
    <>
      <ul className="divide-y border-b last:border-b-0">
        {rows.map((c) => (
          <li key={c.id}>
            <Link href={`/clinics/${clinicId}/calls/${c.id}`}
              className="grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1 px-5 py-3 text-sm hover:bg-muted/60 md:grid-cols-[9rem_9rem_1fr_5rem_1.25rem]">
              <span className="font-medium tabular-nums md:font-normal">{when(c.started_at)}</span>
              <span className="justify-self-end md:justify-self-start"><CallResult call={c} /></span>
              <span className="col-span-2 text-muted-foreground md:col-span-1 md:text-foreground">
                {c.changes.length ? c.changes.map((ch) => (
                  <span key={`${ch.action}${ch.appointment_id}`} className="block">
                    {changeText(ch)}
                    {ch.starts_at && <span className="text-muted-foreground"> · {visitTime(ch.starts_at)}</span>}
                  </span>
                )) : whatHappened(c)}
              </span>
              <span className={cn("text-muted-foreground tabular-nums md:text-foreground", c.duration_s == null && "max-md:hidden")}>{duration(c.duration_s)}</span>
              <ChevronRight className="hidden size-4 text-muted-foreground md:block" aria-hidden />
            </Link>
          </li>
        ))}
      </ul>
      {onMore && rows.length === PAGE && (
        <div className="p-3 text-center">
          <Button variant="outline" onClick={() => onMore(rows[rows.length - 1].id)}>Show older calls</Button>
        </div>
      )}
    </>
  );
}
