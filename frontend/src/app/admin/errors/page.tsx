"use client";
// Vendor errors grouped by vendor and kind, newest first, each linked to the
// calls it hit.
import { useState } from "react";
import Link from "next/link";
import { AlertCircle, CircleCheck } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/app/page-header";
import { DaysPicker, Empty } from "@/components/admin/bits";
import { useErrorGroups, when } from "@/lib/admin";

export default function ErrorsPage() {
  const [days, setDays] = useState(7);
  const groups = useErrorGroups(days);

  return (
    <div className="space-y-5">
      <PageHeader title="Errors" description="Speech, language-model and voice vendor errors, grouped. Retried ones the caller may not have noticed; fatal ones they did."
        actions={<DaysPicker value={days} onChange={setDays} />} />
      {groups.isError ? (
        <Alert variant="destructive"><AlertCircle /><AlertDescription>{groups.error.message}</AlertDescription></Alert>
      ) : !groups.data ? (
        <Skeleton className="h-40" />
      ) : !groups.data.length ? (
        <Empty icon={<CircleCheck className="size-5" />} title="No vendor errors">Every speech, language-model and voice request in this period worked.</Empty>
      ) : (
        <ul className="divide-y overflow-hidden rounded-xl border bg-card">
          {groups.data.map((g) => {
            const fatal = g.detail.includes("fatal");
            return (
              <li key={`${g.name}-${g.detail}`} className="grid gap-2 px-5 py-4 sm:grid-cols-[1fr_auto] sm:items-center">
                <div className="min-w-0">
                  <p className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-[13px] font-medium">{g.name}</span>
                    <span className={fatal ? "rounded-full bg-destructive/10 px-2 py-0.5 text-xs font-medium text-destructive" : "rounded-full bg-warning px-2 py-0.5 text-xs font-medium text-warning-foreground"}>
                      {fatal ? "Fatal" : "Retried"}
                    </span>
                  </p>
                  <p className="mt-0.5 font-mono text-xs text-muted-foreground">{g.detail}</p>
                  <p className="mt-1.5 flex flex-wrap gap-x-3 text-xs">
                    <span className="text-muted-foreground">Calls:</span>
                    {g.call_ids.map((id) => <Link key={id} href={`/admin/calls/${id}`} className="font-medium underline-offset-2 hover:underline">#{id}</Link>)}
                  </p>
                </div>
                <div className="text-sm sm:text-right">
                  <p className="text-2xl font-semibold tabular-nums">{g.count}</p>
                  <p className="text-xs text-muted-foreground">last {when(g.last_at)}</p>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
