"use client";
// One call, end to end: every step with its timing, each tool and whether it
// worked, vendor errors where they happened, how it ended. No words. The
// transcript opens only with a reason, which is logged and shown to the clinic.
import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { AlertCircle, ArrowLeft, CircleCheck, CircleX, LockKeyhole, ShieldAlert, TriangleAlert, Wrench } from "lucide-react";
import { toast } from "sonner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { CallResult } from "@/components/admin/bits";
import { offset, Transcript } from "@/components/calls/transcript";
import { adminKeys, duration, END_REASONS, ms, STAGES, useCallTrace, when } from "@/lib/admin";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { cn } from "@/lib/utils";

export default function CallTracePage() {
  const callId = Number(useParams<{ callId: string }>().callId);
  const trace = useCallTrace(callId);

  return (
    <div className="space-y-6">
      <Link href="/admin/calls" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" aria-hidden /> All calls
      </Link>
      {trace.isError ? (
        <Alert variant="destructive"><AlertCircle /><AlertDescription>{trace.error.message}</AlertDescription></Alert>
      ) : !trace.data ? (
        <div className="space-y-4"><Skeleton className="h-24" /><Skeleton className="h-64" /></div>
      ) : (
        <Body t={trace.data} />
      )}
    </div>
  );
}

function Body({ t }: { t: Schemas["CallTrace"] }) {
  return (
    <>
      <header className="space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">{t.clinic_name}</h1>
          <CallResult call={t} />
        </div>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 rounded-xl border bg-card p-4 text-sm sm:grid-cols-4">
          <Fact label="Started">{when(t.started_at)}</Fact>
          <Fact label="Length">{duration(t.duration_s)}</Fact>
          <Fact label="How it ended">{t.status === "dropped" ? "Never finished: the worker stopped mid-call" : END_REASONS[t.end_reason] ?? (t.end_reason || "Still going")}</Fact>
          <Fact label="Caller spoke">{t.turn_count} times</Fact>
          <div className="col-span-2 sm:col-span-4">
            <dt className="text-xs text-muted-foreground">Vendors</dt>
            <dd className="font-mono text-[13px] break-all">{t.stack}</dd>
          </div>
          {t.appointments.length > 0 && (
            <div className="col-span-2 sm:col-span-4">
              <dt className="text-xs text-muted-foreground">Changed</dt>
              <dd>{t.appointments.map((a) => `Appointment #${a.id} ${a.action}`).join(" · ")}</dd>
            </div>
          )}
        </dl>
      </header>

      <Timeline events={t.events} />
      <TranscriptPanel t={t} />
    </>
  );
}

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="font-medium">{children}</dd>
    </div>
  );
}

function Timeline({ events }: { events: Schemas["TraceEvent"][] }) {
  const max = Math.max(1, ...events.map((e) => e.duration_ms ?? 0));
  return (
    <section aria-labelledby="steps" className="rounded-xl border bg-card">
      <div className="border-b px-5 py-3.5">
        <h2 id="steps" className="font-semibold">Every step</h2>
        <p className="text-sm text-muted-foreground">Timings, tools and errors in order. What was said is not shown here.</p>
      </div>
      {events.length ? (
        <ol className="divide-y">
          {events.map((e, i) => {
            const stage = STAGES[e.kind];
            const Icon = e.kind === "tool" ? Wrench : e.kind === "error" ? TriangleAlert : e.ok ? CircleCheck : CircleX;
            return (
              <li key={i} className={cn("grid grid-cols-[3rem_1fr_auto] items-center gap-3 px-5 py-2.5 text-sm", !e.ok && "bg-destructive/5")}>
                <span className="text-xs text-muted-foreground tabular-nums">{offset(e.t_ms)}</span>
                <div className="min-w-0">
                  <p className="flex items-center gap-2">
                    <Icon className={cn("size-4 shrink-0", e.ok ? "text-muted-foreground" : "text-destructive")} aria-hidden />
                    <span className="font-medium">{e.kind === "tool" ? <span className="font-mono text-[13px]">{e.name}</span> : e.kind === "error" ? "Vendor error" : stage?.label ?? e.kind}</span>
                    {e.kind === "error" && <span className="font-mono text-[13px] text-muted-foreground">{e.name}</span>}
                    {e.kind === "tool" && <span className={cn("text-xs", e.ok ? "text-success-foreground" : "text-destructive")}>{e.ok ? "worked" : "refused"}</span>}
                  </p>
                  {(e.detail || stage) && (
                    <p className="truncate pl-6 text-xs text-muted-foreground">{[stage?.hint, e.detail].filter(Boolean).join(" · ")}</p>
                  )}
                  {e.duration_ms != null && (
                    <div className="mt-1 ml-6 h-1 max-w-sm overflow-hidden rounded-full bg-muted">
                      <div className={cn("h-full rounded-full", e.duration_ms > 2000 ? "bg-destructive/70" : "bg-foreground/50")}
                        style={{ width: `${(e.duration_ms / max) * 100}%` }} />
                    </div>
                  )}
                </div>
                <span className="text-right tabular-nums">{ms(e.duration_ms)}</span>
              </li>
            );
          })}
        </ol>
      ) : <p className="px-5 py-4 text-sm text-muted-foreground">No steps recorded.</p>}
    </section>
  );
}

function TranscriptPanel({ t }: { t: Schemas["CallTrace"] }) {
  const queryClient = useQueryClient();
  const [asking, setAsking] = useState(false);
  const [reason, setReason] = useState("");
  const [items, setItems] = useState<Schemas["TranscriptItem"][] | null>(null);
  const [busy, setBusy] = useState(false);

  const open = async () => {
    setBusy(true);
    try {
      const got = await unwrap(api.POST("/api/admin/calls/{call_id}/transcript", {
        params: { path: { call_id: t.id } }, body: { reason },
      }));
      setItems(got);
      setAsking(false);
      await queryClient.invalidateQueries({ queryKey: adminKeys.call(t.id) });
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section aria-labelledby="transcript" className="rounded-xl border bg-card">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b px-5 py-3.5">
        <div>
          <h2 id="transcript" className="flex items-center gap-2 font-semibold"><LockKeyhole className="size-4" aria-hidden /> What was said</h2>
          <p className="max-w-xl text-sm text-muted-foreground">
            {t.transcript_kept
              ? "Patient data. Opening it is logged with your reason, and the clinic can see that you did."
              : "Deleted after 30 days, as every transcript is. The steps above are kept."}
          </p>
        </div>
        {t.transcript_kept && !items && (
          <Button variant="outline" onClick={() => setAsking(true)}><ShieldAlert /> Open for debugging</Button>
        )}
      </div>
      {items && <div className="p-5"><Transcript items={items} /></div>}
      {t.accesses.length > 0 && (
        <div className="border-t px-5 py-3.5">
          <p className="mb-2 text-xs font-medium text-muted-foreground">Opened before</p>
          <ul className="space-y-1 text-sm">
            {t.accesses.map((a, i) => (
              <li key={i}><span className="font-medium">{a.email}</span> · {when(a.at)} · <span className="text-muted-foreground">“{a.reason}”</span></li>
            ))}
          </ul>
        </div>
      )}

      <Dialog open={asking} onOpenChange={setAsking}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Why do you need to read this call?</DialogTitle>
            <DialogDescription>
              {t.clinic_name} will see your email, the time and this reason next to the call.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="reason">Reason</Label>
            <Textarea id="reason" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300}
              placeholder="e.g. The receptionist booked the wrong day; checking what it heard" />
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setAsking(false)}>Cancel</Button>
            <Button onClick={open} disabled={busy || reason.trim().length < 5}>Log reason and open</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
