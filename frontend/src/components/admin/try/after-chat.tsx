"use client";
// Once a chat has ended: what it did, what it cost, and erasing it. The
// numbers come from the chat's own call record (the same trace page every
// call has).
import Link from "next/link";
import { Eraser, ListTree } from "lucide-react";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { CallResult } from "@/components/admin/bits";
import { useCallTrace } from "@/lib/admin";
import { quantity, rupees } from "@/lib/costs";
import { useEraseTry } from "@/lib/try";

export function AfterChat({ callId, onErased }: { callId: number; onErased: () => void }) {
  const trace = useCallTrace(callId);
  const erase = useEraseTry();
  const t = trace.data;
  const tokens = t?.cost?.lines.filter((l) => l.part === "thinking").reduce((sum, l) => sum + l.quantity, 0) ?? 0;
  return (
    <section aria-labelledby="after-chat" className="space-y-4 rounded-xl border bg-card p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="after-chat" className="font-semibold">What this chat did</h2>
        {t && <CallResult call={t} />}
      </div>
      {trace.isError ? (
        <p className="text-sm text-destructive">{trace.error.message}</p>
      ) : !t ? (
        <Skeleton className="h-12" />
      ) : (
        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-xs text-muted-foreground">Diary</dt>
            <dd>{t.appointments.length ? t.appointments.map((a) => `Appointment #${a.id} ${a.action}`).join(" · ") : "Nothing booked, moved or cancelled"}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Brain</dt>
            <dd className="font-mono text-[13px]">{t.stack.replace(/^text · /, "")}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Cost</dt>
            <dd className="tabular-nums">
              {t.cost ? rupees(t.cost.rupees) : "Not recorded"}
              {tokens > 0 && <span className="text-muted-foreground"> · {quantity(tokens)} tokens</span>}
              {t.cost && !t.cost.complete && <span className="block text-xs text-destructive">incomplete: a price is missing</span>}
            </dd>
          </div>
        </dl>
      )}
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" asChild>
          <Link href={`/admin/calls/${callId}`}><ListTree /> Timings and full trace</Link>
        </Button>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button variant="outline" className="text-destructive hover:text-destructive" disabled={erase.isPending}>
              <Eraser /> Erase this chat
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Erase this chat?</AlertDialogTitle>
              <AlertDialogDescription>
                Every appointment it booked, moved or cancelled goes back to how it was, and its record and
                conversation are deleted. Its cost stays on the Costs page. This can&apos;t be undone.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Keep it</AlertDialogCancel>
              <AlertDialogAction className="bg-destructive text-white hover:bg-destructive/90"
                onClick={() => erase.mutate(callId, { onSuccess: onErased })}>
                Yes, erase it
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </section>
  );
}
