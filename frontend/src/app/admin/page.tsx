"use client";
// Health: is the receptionist working, everywhere? Calls and how they ended,
// what needs a look, how long each step takes per vendor stack, and which
// vendors are failing.
import { useState } from "react";
import Link from "next/link";
import { AlertCircle, CircleCheck, Moon, TriangleAlert, Unplug } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/app/page-header";
import { DaysPicker, Stat } from "@/components/admin/bits";
import { ms, OUTCOMES, STAGES, useHealth, vendorsOf } from "@/lib/admin";
import type { Schemas } from "@/lib/api/client";

export default function HealthPage() {
  const [days, setDays] = useState(7);
  const health = useHealth(days);

  return (
    <div className="space-y-6">
      <PageHeader title="Health" description="Every clinic's receptionist: what calls did, what failed, and how fast it answers."
        actions={<DaysPicker value={days} onChange={setDays} />} />
      {health.isError ? (
        <Alert variant="destructive"><AlertCircle /><AlertDescription>{health.error.message}</AlertDescription></Alert>
      ) : !health.data ? (
        <div className="space-y-4"><Skeleton className="h-28" /><Skeleton className="h-48" /></div>
      ) : (
        <Body h={health.data} />
      )}
    </div>
  );
}

function Body({ h }: { h: Schemas["Health"] }) {
  const period = h.days === 1 ? "last 24 hours" : `last ${h.days} days`;
  const changed = (h.outcomes.booked ?? 0) + (h.outcomes.moved ?? 0) + (h.outcomes.cancelled ?? 0);
  return (
    <>
      <div className="grid grid-cols-2 divide-x divide-y overflow-hidden rounded-xl border bg-card sm:grid-cols-4 sm:divide-y-0">
        <Stat label="Calls" value={h.calls} hint={`${h.calls_today} today · ${period}`} />
        <Stat label="Bookings changed" value={changed}
          hint={`${h.outcomes.booked ?? 0} booked · ${h.outcomes.moved ?? 0} moved · ${h.outcomes.cancelled ?? 0} cancelled`} />
        <Stat label="Dropped calls" value={h.dropped} hint="never finished" tone={h.dropped ? "bad" : undefined} />
        <Stat label="Calls with vendor errors" value={h.with_errors} hint="retried or fatal" tone={h.with_errors ? "bad" : undefined} />
      </div>

      <section aria-labelledby="attention" className="rounded-xl border bg-card">
        <h2 id="attention" className="border-b px-5 py-3.5 font-semibold">Needs a look</h2>
        {h.attention.length ? (
          <ul className="divide-y">
            {h.attention.map((a, i) => <AttentionRow key={i} a={a} />)}
          </ul>
        ) : (
          <p className="flex items-center gap-2 px-5 py-4 text-sm text-muted-foreground">
            <CircleCheck className="size-4 text-success-foreground" aria-hidden /> Nothing needs a look: no dropped or failed calls, no vendor errors.
          </p>
        )}
      </section>

      <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        <Latency stages={h.stages} />
        <section aria-labelledby="outcomes" className="rounded-xl border bg-card">
          <h2 id="outcomes" className="border-b px-5 py-3.5 font-semibold">How calls ended</h2>
          {h.calls ? (
            <ul className="space-y-3 p-5">
              {Object.entries(OUTCOMES).map(([key, label]) => {
                const n = h.outcomes[key] ?? 0;
                return (
                  <li key={key}>
                    <div className="flex justify-between text-sm"><span>{label}</span><span className="tabular-nums">{n}</span></div>
                    <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
                      <div className={key === "failed" ? "h-full bg-destructive" : "h-full bg-foreground/70"}
                        style={{ width: `${(n / Math.max(1, h.calls)) * 100}%` }} />
                    </div>
                  </li>
                );
              })}
            </ul>
          ) : <p className="px-5 py-4 text-sm text-muted-foreground">No calls in this period.</p>}
        </section>
      </div>

      <section aria-labelledby="vendors" className="rounded-xl border bg-card">
        <h2 id="vendors" className="border-b px-5 py-3.5 font-semibold">Vendor errors</h2>
        {h.vendors.length ? (
          <ul className="divide-y">
            {h.vendors.map((v) => (
              <li key={v.name} className="flex items-center justify-between gap-4 px-5 py-3 text-sm">
                <span className="font-mono text-[13px]">{v.name}</span>
                <span className="text-muted-foreground"><b className="text-foreground tabular-nums">{v.errors}</b> {v.errors === 1 ? "error" : "errors"} in {v.calls} {v.calls === 1 ? "call" : "calls"}</span>
              </li>
            ))}
          </ul>
        ) : <p className="px-5 py-4 text-sm text-muted-foreground">No vendor errors in this period.</p>}
      </section>
    </>
  );
}

function AttentionRow({ a }: { a: Schemas["Attention"] }) {
  const Icon = a.kind === "dropped" ? Unplug : a.kind === "quiet" ? Moon : TriangleAlert;
  const href = a.call_id ? `/admin/calls/${a.call_id}` : a.kind === "errors" ? "/admin/errors" : a.clinic_id ? `/admin/clinics/${a.clinic_id}` : null;
  const body = (
    <>
      <Icon className={a.kind === "quiet" ? "size-4 shrink-0 text-muted-foreground" : "size-4 shrink-0 text-destructive"} aria-hidden />
      <span className="flex-1">{a.text}</span>
      {href && <span className="text-xs font-medium text-muted-foreground">Open</span>}
    </>
  );
  return (
    <li>
      {href
        ? <Link href={href} className="flex items-center gap-3 px-5 py-3 text-sm hover:bg-muted/60">{body}</Link>
        : <div className="flex items-center gap-3 px-5 py-3 text-sm">{body}</div>}
    </li>
  );
}

/** p50 and p95 per step and vendor stack, as bars on one scale. */
function Latency({ stages }: { stages: Schemas["Stage"][] }) {
  const max = Math.max(1, ...stages.map((s) => s.p95_ms));
  // One vendor stack: name it once. Several (production and testing): per row, to compare.
  const stacks = [...new Set(stages.map((s) => s.stack))];
  return (
    <section aria-labelledby="latency" className="rounded-xl border bg-card">
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b px-5 py-3.5">
        <div>
          <h2 id="latency" className="font-semibold">How fast it answers</h2>
          {stacks.length === 1 && <p className="font-mono text-xs text-muted-foreground">{stacks[0]}</p>}
        </div>
        <p className="flex items-center gap-3 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-foreground/80" /> typical (p50)</span>
          <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-foreground/20" /> slow calls (p95)</span>
        </p>
      </div>
      {stages.length ? (
        <ul className="space-y-4 p-5">
          {stages.map((s) => (
            <li key={`${s.stage}-${s.stack}`}>
              <div className="flex flex-wrap items-baseline justify-between gap-x-3 text-sm">
                <span>
                  <span className="font-medium">{STAGES[s.stage]?.label ?? s.stage}</span>
                  <span className="ml-2 text-xs text-muted-foreground">{STAGES[s.stage]?.hint}{stacks.length > 1 && ` · ${vendorsOf(s.stack)}`}</span>
                </span>
                <span className="tabular-nums">{ms(s.p50_ms)} <span className="text-muted-foreground">/ {ms(s.p95_ms)}</span></span>
              </div>
              <div className="relative mt-1.5 h-2 overflow-hidden rounded-full bg-muted" title={`${s.count} measurements`}>
                <div className="absolute inset-y-0 left-0 rounded-full bg-foreground/20" style={{ width: `${(s.p95_ms / max) * 100}%` }} />
                <div className="absolute inset-y-0 left-0 rounded-full bg-foreground/80" style={{ width: `${(s.p50_ms / max) * 100}%` }} />
              </div>
            </li>
          ))}
        </ul>
      ) : <p className="px-5 py-4 text-sm text-muted-foreground">No timings yet. They appear after the first calls.</p>}
    </section>
  );
}
