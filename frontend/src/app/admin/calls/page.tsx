"use client";
// Every call, every clinic, newest first: what it did and whether anything
// went wrong. Opens to the call's trace. No words from any call here.
import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AlertCircle, ChevronRight, PhoneOff, TriangleAlert } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { PageHeader } from "@/components/app/page-header";
import { CallResult, Empty } from "@/components/admin/bits";
import { duration, OUTCOMES, useAdminClinics, useCalls, vendorsOf, when, type CallFilters } from "@/lib/admin";

const PAGE = 50; // the API's page size

export default function Page() {
  return <Suspense fallback={<Skeleton className="h-64" />}><CallsPage /></Suspense>;
}

function CallsPage() {
  const clinics = useAdminClinics();
  const fromLink = Number(useSearchParams().get("clinic")) || undefined; // "Its calls" on a clinic's page
  const [filters, setFilters] = useState<CallFilters>({ clinic_id: fromLink });
  const [cursors, setCursors] = useState<(number | undefined)[]>([undefined]);
  const set = (next: CallFilters) => { setFilters(next); setCursors([undefined]); };

  return (
    <div className="space-y-5">
      <PageHeader title="Calls" description="Every call to every clinic. Open one to see each step it took." />

      <div className="flex flex-wrap items-center gap-3 rounded-xl border bg-card p-3">
        <Select value={filters.clinic_id ? String(filters.clinic_id) : "all"}
          onValueChange={(v) => set({ ...filters, clinic_id: v === "all" ? undefined : Number(v) })}>
          <SelectTrigger aria-label="Clinic" className="w-full sm:w-56"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All clinics</SelectItem>
            {clinics.data?.map((c) => <SelectItem key={c.id} value={String(c.id)}>{c.name}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={filters.outcome ?? "all"} disabled={filters.status === "dropped"}
          onValueChange={(v) => set({ ...filters, outcome: v === "all" ? undefined : v })}>
          <SelectTrigger aria-label="Result" className="w-full sm:w-44"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Any result</SelectItem>
            {Object.entries(OUTCOMES).map(([k, label]) => <SelectItem key={k} value={k}>{label}</SelectItem>)}
          </SelectContent>
        </Select>
        <div className="flex items-center gap-2">
          <Switch id="errors" checked={!!filters.with_errors} onCheckedChange={(on) => set({ ...filters, with_errors: on || undefined })} />
          <Label htmlFor="errors">Vendor errors only</Label>
        </div>
        <div className="flex items-center gap-2">
          <Switch id="dropped" checked={filters.status === "dropped"}
            onCheckedChange={(on) => set({ ...filters, status: on ? "dropped" : undefined, outcome: on ? undefined : filters.outcome })} />
          <Label htmlFor="dropped">Dropped only</Label>
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border bg-card">
        <div className="hidden grid-cols-[9rem_1fr_9rem_5rem_4rem_5.5rem_1.25rem] gap-4 border-b bg-muted/50 px-5 py-2.5 text-xs font-medium text-muted-foreground md:grid">
          <span>When</span><span>Clinic</span><span>Result</span><span>Length</span><span>Turns</span><span>Problems</span><span />
        </div>
        {cursors.map((cursor, i) => (
          <CallRows key={cursor ?? "first"} filters={filters} beforeId={cursor} first={i === 0}
            onMore={i === cursors.length - 1 ? (last) => setCursors([...cursors, last]) : undefined} />
        ))}
      </div>
    </div>
  );
}

function CallRows({ filters, beforeId, first, onMore }: {
  filters: CallFilters; beforeId?: number; first: boolean; onMore?: (lastId: number) => void;
}) {
  const calls = useCalls(filters, beforeId);
  if (calls.isError) return <Alert variant="destructive" className="m-3 w-auto"><AlertCircle /><AlertDescription>{calls.error.message}</AlertDescription></Alert>;
  if (!calls.data) return <div className="space-y-2 p-4">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-10" />)}</div>;
  if (first && !calls.data.length) {
    return (
      <div className="p-4">
        <Empty icon={<PhoneOff className="size-5" />} title="No calls match">
          Calls appear here as soon as they start. Try another clinic or clear the filters.
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
            <Link href={`/admin/calls/${c.id}`}
              className="grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1 px-5 py-3 text-sm hover:bg-muted/60 md:grid-cols-[9rem_1fr_9rem_5rem_4rem_5.5rem_1.25rem]">
              <span className="tabular-nums md:order-none">{when(c.started_at)}</span>
              <span className="order-3 col-span-2 truncate text-muted-foreground md:order-none md:col-span-1 md:text-foreground">
                {c.clinic_name} <span className="ml-1 text-xs text-muted-foreground">{vendorsOf(c.stack)}</span>
              </span>
              <span className="order-2 justify-self-end md:order-none md:justify-self-start"><CallResult call={c} /></span>
              <span className="order-4 text-muted-foreground tabular-nums md:order-none md:text-foreground">{duration(c.duration_s)}</span>
              <span className="order-5 hidden tabular-nums md:order-none md:inline">{c.turn_count}</span>
              <span className="order-6 md:order-none">
                {c.error_count || c.tool_failures ? (
                  <span className="inline-flex items-center gap-1 text-xs font-medium text-destructive">
                    <TriangleAlert className="size-3.5" aria-hidden />
                    {[c.error_count && `${c.error_count} vendor`, c.tool_failures && `${c.tool_failures} tool`].filter(Boolean).join(", ")}
                  </span>
                ) : <span className="text-xs text-muted-foreground">None</span>}
              </span>
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
