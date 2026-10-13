"use client";
// Costs: what the receptionist costs to run, in rupees. A month's total and
// what is actually paid after free allowances, where the money goes, the
// most expensive calls, and a check against each vendor's own bill.
import { useState } from "react";
import Link from "next/link";
import { AlertCircle, ChevronRight, CircleCheck, IndianRupee, Settings2, TriangleAlert } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/app/page-header";
import { Empty, Stat } from "@/components/admin/bits";
import { when } from "@/lib/admin";
import { languageName } from "@/lib/calls";
import { money, monthName, PARTS, quantity, rupees, useCostMonth, VENDORS } from "@/lib/costs";
import type { Schemas } from "@/lib/api/client";
import { cn } from "@/lib/utils";

export default function CostsPage() {
  const [month, setMonth] = useState<string | null>(null);
  const costs = useCostMonth(month);
  const months = costs.data?.months ?? [];

  return (
    <div className="space-y-6">
      <PageHeader title="Costs" description="What every call costs you in rupees, worked out from exactly what it used and your price list."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {months.length > 0 && (
              <Select value={costs.data?.month} onValueChange={setMonth}>
                <SelectTrigger aria-label="Month" className="w-44"><SelectValue /></SelectTrigger>
                <SelectContent>{months.map((m) => <SelectItem key={m} value={m}>{monthName(m)}</SelectItem>)}</SelectContent>
              </Select>
            )}
            <Button variant="outline" asChild><Link href="/admin/costs/prices"><Settings2 /> Prices</Link></Button>
          </div>
        } />
      {costs.isError ? (
        <Alert variant="destructive"><AlertCircle /><AlertDescription>{costs.error.message}</AlertDescription></Alert>
      ) : !costs.data ? (
        <div className="space-y-4"><Skeleton className="h-28" /><Skeleton className="h-64" /></div>
      ) : (
        <Body m={costs.data} />
      )}
    </div>
  );
}

function Body({ m }: { m: Schemas["CostMonth"] }) {
  const nothing = m.usage_rupees === 0 && m.calls + m.test_calls === 0 && m.fixed.length === 0;
  return (
    <>
      {m.missing.length > 0 && <Missing missing={m.missing} />}

      <div className="grid grid-cols-2 divide-x divide-y overflow-hidden rounded-xl border bg-card sm:grid-cols-4 sm:divide-y-0">
        <Stat label="You pay this month" value={rupees(m.to_pay_rupees)}
          hint={m.free_rupees > 0 ? `after ${rupees(m.free_rupees)} free` : "nothing free used"} />
        <Stat label="Full price of what was used" value={rupees(m.usage_rupees)}
          hint={m.fixed_rupees > 0 ? `plus ${rupees(m.fixed_rupees)} monthly fees` : "before free allowances"} />
        <Stat label="Calls" value={m.calls} hint={m.test_calls ? `plus ${m.test_calls} staff test ${m.test_calls === 1 ? "call" : "calls"}` : "from patients"} />
        <Stat label="Average call" value={m.per_call_rupees == null ? "—" : rupees(m.per_call_rupees)}
          hint={m.other_rupees > 0 ? `${rupees(m.other_rupees)} other costs` : "full price"} />
      </div>

      {nothing ? (
        <Empty icon={<IndianRupee className="size-5" />} title={`Nothing used in ${monthName(m.month)}`}>
          {m.tracked_since ? "No calls or other costs this month." : "Costs are recorded from the first call after this feature started. Make a call and it shows here."}
        </Empty>
      ) : (
        <>
          <Daily m={m} />
          <div className="grid gap-6 lg:grid-cols-2">
            <Split title="Where the money goes" slices={m.by_part} />
            <Split title="By vendor" slices={m.by_vendor} />
            <Split title="By language" slices={m.by_language} calls />
            <Split title="By clinic" slices={m.by_clinic} calls />
          </div>
          <TopCalls calls={m.top_calls} />
          <div className="grid gap-6 lg:grid-cols-2">
            <FreeAndFees m={m} />
            <Bills m={m} />
          </div>
        </>
      )}
      {m.tracked_since && (
        <p className="text-xs text-muted-foreground">Costs recorded since {when(m.tracked_since)}. Calls before that show no cost.</p>
      )}
    </>
  );
}

function Missing({ missing }: { missing: Schemas["MissingPrice"][] }) {
  return (
    <Alert variant="destructive">
      <TriangleAlert />
      <AlertTitle>Some costs are incomplete</AlertTitle>
      <AlertDescription>
        <ul className="list-disc pl-4">
          {missing.map((x, i) => (
            <li key={i}>
              {x.why === "rate"
                ? "No dollar-to-rupee rate covers some of this month."
                : `${VENDORS[x.provider] ?? x.provider} ${x.model || ""} has no price for ${x.unit_label}.`}
            </li>
          ))}
        </ul>
        <Link href="/admin/costs/prices" className="mt-1 inline-block font-medium underline">Add it in Prices</Link>
      </AlertDescription>
    </Alert>
  );
}

/** One bar per day, one hue: magnitude only. Hover (or focus) for the amount. */
function Daily({ m }: { m: Schemas["CostMonth"] }) {
  const [y, mo] = m.month.split("-").map(Number);
  const days = new Date(y, mo, 0).getDate();
  const byDay = new Map(m.by_day.map((d) => [Number(d.day.slice(8, 10)), d.rupees]));
  const max = Math.max(0.0001, ...m.by_day.map((d) => d.rupees));
  const [hover, setHover] = useState<number | null>(null);
  return (
    <section aria-labelledby="daily" className="rounded-xl border bg-card">
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b px-5 py-3.5">
        <h2 id="daily" className="font-semibold">Each day</h2>
        <p className="text-sm text-muted-foreground tabular-nums">
          {hover ? `${hover} ${monthName(m.month).split(" ")[0]}: ${rupees(byDay.get(hover) ?? 0)}` : "Point at a day to see its cost"}
        </p>
      </div>
      <div className="flex h-36 items-end gap-0.5 px-5 pt-4 pb-1" role="list" aria-label="Cost each day">
        {Array.from({ length: days }, (_, i) => i + 1).map((d) => {
          const v = byDay.get(d) ?? 0;
          return (
            <button key={d} type="button" role="listitem" aria-label={`${d} ${monthName(m.month)}: ${rupees(v)}`}
              onMouseEnter={() => setHover(d)} onMouseLeave={() => setHover(null)} onFocus={() => setHover(d)} onBlur={() => setHover(null)}
              className="group flex h-full flex-1 items-end outline-none">
              <span className={cn("block w-full rounded-t-[4px] bg-foreground/60 transition-colors group-hover:bg-foreground group-focus-visible:bg-foreground",
                v === 0 && "bg-muted")} style={{ height: v ? `max(3px, ${(v / max) * 100}%)` : "2px" }} />
            </button>
          );
        })}
      </div>
      <div className="flex justify-between px-5 pb-3 text-xs text-muted-foreground tabular-nums">
        <span>1</span><span>{Math.ceil(days / 2)}</span><span>{days}</span>
      </div>
    </section>
  );
}

function Split({ title, slices, calls }: { title: string; slices: Schemas["CostSlice"][]; calls?: boolean }) {
  const total = slices.reduce((sum, s) => sum + s.rupees, 0);
  return (
    <section className="rounded-xl border bg-card">
      <h2 className="border-b px-5 py-3.5 font-semibold">{title}</h2>
      {slices.length ? (
        <ul className="space-y-3 p-5">
          {slices.map((s) => (
            <li key={s.key}>
              <div className="flex justify-between gap-3 text-sm">
                <span>{s.label}{calls && s.calls > 0 && <span className="text-muted-foreground"> · {s.calls} {s.calls === 1 ? "call" : "calls"}</span>}</span>
                <span className="tabular-nums">{rupees(s.rupees)}</span>
              </div>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full bg-foreground/70" style={{ width: `${total ? (s.rupees / total) * 100 : 0}%` }} />
              </div>
            </li>
          ))}
        </ul>
      ) : <p className="px-5 py-4 text-sm text-muted-foreground">Nothing this month.</p>}
    </section>
  );
}

function TopCalls({ calls }: { calls: Schemas["CallCost"][] }) {
  return (
    <section aria-labelledby="top" className="rounded-xl border bg-card">
      <div className="border-b px-5 py-3.5">
        <h2 id="top" className="font-semibold">Calls, most expensive first</h2>
        <p className="text-sm text-muted-foreground">Open one to see what each part cost.</p>
      </div>
      {calls.length ? (
        <ul className="divide-y">
          {calls.map((c, i) => {
            const body = (
              <>
                <div className="min-w-0">
                  <p className="truncate font-medium">
                    {c.clinic_name || "Deleted clinic"}
                    {c.test && <span className="ml-2 rounded-full bg-muted px-2 py-0.5 text-xs font-normal text-muted-foreground">Test call</span>}
                  </p>
                  <p className="truncate text-xs text-muted-foreground">
                    {when(c.started_at)}{languageName(c.language) && ` · ${languageName(c.language)}`}
                    {" · "}{Object.entries(c.parts).filter(([, v]) => v > 0).map(([k, v]) => `${PARTS[k] ?? k} ${rupees(v)}`).join(" · ") || "nothing priced"}
                    {c.call_id == null && " · call erased"}
                  </p>
                </div>
                <span className="text-right font-semibold tabular-nums">
                  {rupees(c.rupees)}
                  {!c.complete && <span className="block text-xs font-normal text-destructive">incomplete</span>}
                </span>
                {c.call_id != null ? <ChevronRight className="size-4 text-muted-foreground" aria-hidden /> : <span />}
              </>
            );
            const cls = "grid grid-cols-[1fr_auto_1rem] items-center gap-3 px-5 py-3 text-sm";
            return (
              <li key={c.call_id ?? `gone-${i}`}>
                {c.call_id != null
                  ? <Link href={`/admin/calls/${c.call_id}`} className={cn(cls, "hover:bg-muted/60")}>{body}</Link>
                  : <div className={cls}>{body}</div>}
              </li>
            );
          })}
        </ul>
      ) : <p className="px-5 py-4 text-sm text-muted-foreground">No calls this month.</p>}
    </section>
  );
}

function FreeAndFees({ m }: { m: Schemas["CostMonth"] }) {
  return (
    <section className="rounded-xl border bg-card">
      <div className="border-b px-5 py-3.5">
        <h2 className="font-semibold">Free allowances and monthly fees</h2>
        <p className="text-sm text-muted-foreground">Free usage your plans include, and fees you pay whatever the usage.</p>
      </div>
      <ul className="divide-y text-sm">
        {m.free.map((f, i) => (
          <li key={`f${i}`} className="px-5 py-3">
            <div className="flex justify-between gap-3">
              <span>{VENDORS[f.provider] ?? f.provider}: {quantity(Math.min(f.used, f.allowance))} of {quantity(f.allowance)} free {f.unit_label}</span>
              <span className="tabular-nums text-success-foreground">{f.rupees > 0 ? "−" : ""}{rupees(f.rupees)}</span>
            </div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
              <div className={cn("h-full rounded-full", f.used >= f.allowance ? "bg-destructive/70" : "bg-foreground/60")}
                style={{ width: `${Math.min(100, f.allowance ? (f.used / f.allowance) * 100 : 0)}%` }} />
            </div>
            {f.used > f.allowance && <p className="mt-1 text-xs text-destructive">Used up: {quantity(f.used - f.allowance)} {f.unit_label} beyond it.</p>}
          </li>
        ))}
        {m.fixed.map((f, i) => (
          <li key={`x${i}`} className="flex justify-between gap-3 px-5 py-3">
            <span>{f.name} <span className="text-muted-foreground">· {VENDORS[f.provider] ?? f.provider}</span></span>
            <span className="tabular-nums">{rupees(f.rupees)}</span>
          </li>
        ))}
        {!m.free.length && !m.fixed.length && <li className="px-5 py-4 text-muted-foreground">None set. Add them in Prices.</li>}
      </ul>
    </section>
  );
}

function Bills({ m }: { m: Schemas["CostMonth"] }) {
  return (
    <section className="rounded-xl border bg-card">
      <div className="border-b px-5 py-3.5">
        <h2 className="font-semibold">Check against the vendors&apos; bills</h2>
        <p className="text-sm text-muted-foreground">Type each vendor&apos;s bill for the month in Prices. A gap means a price here is wrong.</p>
      </div>
      {m.bills.length ? (
        <ul className="divide-y text-sm">
          {m.bills.map((b) => {
            const gap = b.ours == null ? null : b.theirs - b.ours;
            const close = gap != null && Math.abs(gap) <= Math.max(0.01, b.theirs * 0.05);
            return (
              <li key={b.provider} className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-0.5 px-5 py-3">
                <span className="font-medium">{VENDORS[b.provider] ?? b.provider}</span>
                <span className={cn("flex items-center gap-1.5 text-xs font-medium", close ? "text-success-foreground" : "text-destructive")}>
                  {close ? <CircleCheck className="size-3.5" aria-hidden /> : <TriangleAlert className="size-3.5" aria-hidden />}
                  {gap == null ? "Can't compare: a price is missing" : close ? "Matches" : `Off by ${money(Math.abs(gap), b.currency)}`}
                </span>
                <span className="col-span-2 text-muted-foreground tabular-nums">
                  Their bill {money(b.theirs, b.currency)} · ours {b.ours == null ? "—" : money(b.ours, b.currency)}
                </span>
              </li>
            );
          })}
        </ul>
      ) : <p className="px-5 py-4 text-sm text-muted-foreground">No bills typed in for {monthName(m.month)} yet.</p>}
    </section>
  );
}
