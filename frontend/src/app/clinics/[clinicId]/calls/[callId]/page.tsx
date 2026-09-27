"use client";
// One call as the clinic sees it: when, what it changed, and what the caller
// and the receptionist said. Plus every time ClinicDesk support opened it.
import Link from "next/link";
import { useParams } from "next/navigation";
import { AlertCircle, ArrowLeft, Eye, MessagesSquare } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { CallResult } from "@/components/admin/bits";
import { Transcript } from "@/components/calls/transcript";
import { duration, when } from "@/lib/admin";
import type { Schemas } from "@/lib/api/client";
import { changeText, visitTime, whatHappened } from "@/lib/calls";
import { PRODUCT_NAME } from "@/lib/product";
import { useClinicCall } from "@/lib/queries";

export default function CallPage() {
  const params = useParams<{ clinicId: string; callId: string }>();
  const clinicId = Number(params.clinicId);
  const call = useClinicCall(clinicId, Number(params.callId));
  return (
    <div className="space-y-6">
      <Link href={`/clinics/${clinicId}/calls`} className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" aria-hidden /> All calls
      </Link>
      {call.isError ? (
        <Alert variant="destructive"><AlertCircle /><AlertDescription>{call.error.message}</AlertDescription></Alert>
      ) : !call.data ? (
        <div className="space-y-4"><Skeleton className="h-24" /><Skeleton className="h-64" /></div>
      ) : (
        <Body clinicId={clinicId} call={call.data} />
      )}
    </div>
  );
}

function Body({ clinicId, call }: { clinicId: number; call: Schemas["ClinicCallDetail"] }) {
  return (
    <>
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">Call · {when(call.started_at)}</h1>
        <CallResult call={call} />
      </div>

      <section className="grid gap-4 rounded-xl border bg-card p-5 sm:grid-cols-[10rem_1fr]">
        <div>
          <p className="text-xs text-muted-foreground">Length</p>
          <p className="font-medium tabular-nums">{duration(call.duration_s)}</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">What happened</p>
          {call.changes.length ? (
            <ul className="space-y-0.5">
              {call.changes.map((c) => (
                <li key={`${c.action}${c.appointment_id}`} className="font-medium">
                  {changeText(c)}
                  {c.starts_at && (
                    <> · <Link className="text-primary hover:underline"
                      href={`/clinics/${clinicId}/appointments?day=${c.starts_at.slice(0, 10)}`}>{visitTime(c.starts_at)}</Link></>
                  )}
                </li>
              ))}
            </ul>
          ) : <p className="font-medium">{whatHappened(call)}</p>}
        </div>
      </section>

      {call.support_views.length > 0 && (
        <section aria-labelledby="support" className="rounded-xl border border-warning bg-warning/30 p-5">
          <h2 id="support" className="flex items-center gap-2 font-semibold"><Eye className="size-4" aria-hidden /> Viewed by {PRODUCT_NAME} support</h2>
          <p className="mt-1 text-sm text-muted-foreground">Support opens a call only to fix a problem, and always records why.</p>
          <ul className="mt-3 space-y-1.5 text-sm">
            {call.support_views.map((v, i) => (
              <li key={i}><span className="tabular-nums text-muted-foreground">{when(v.at)}</span> · “{v.reason}”</li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="said" className="rounded-xl border bg-card">
        <div className="border-b px-5 py-4">
          <h2 id="said" className="flex items-center gap-2 font-semibold"><MessagesSquare className="size-4" aria-hidden /> What was said</h2>
          <p className="text-sm text-muted-foreground">Kept for 30 days, then deleted.</p>
        </div>
        <div className="p-5">
          {call.transcript_kept
            ? <Transcript items={call.conversation} showTools={false} />
            : <p className="text-sm text-muted-foreground">The words of this call were deleted after 30 days.</p>}
        </div>
      </section>
    </>
  );
}
