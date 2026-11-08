"use client";
// Prices: everything the costs are worked out from, edited here and never in
// code. Vendors' prices (one row per model, dated so the past keeps its own),
// the dollar rate, free allowances, monthly fees, and each month's real bills
// to check against.
import Link from "next/link";
import { AlertCircle, ArrowLeft } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/app/page-header";
import { CostSection } from "@/components/admin/prices/cost-section";
import { PriceSection } from "@/components/admin/prices/price-section";
import { day, thisMonth, today } from "@/components/admin/prices/row-form";
import { money, monthName, quantity, useCostSettings, VENDORS } from "@/lib/costs";
import type { Schemas } from "@/lib/api/client";

export default function PricesPage() {
  const settings = useCostSettings();
  return (
    <div className="space-y-6">
      <Link href="/admin/costs" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" aria-hidden /> Costs
      </Link>
      <PageHeader title="Prices" description="What the costs are worked out from. Change anything here: no code, and every call it covers is priced again." />
      {settings.isError ? (
        <Alert variant="destructive"><AlertCircle /><AlertDescription>{settings.error.message}</AlertDescription></Alert>
      ) : !settings.data ? (
        <div className="space-y-4"><Skeleton className="h-40" /><Skeleton className="h-72" /></div>
      ) : (
        <Body s={settings.data} />
      )}
    </div>
  );
}

const vendor = (p: string) => VENDORS[p] ?? p;

function Body({ s }: { s: Schemas["CostSettings"] }) {
  const units = s.units;
  return (
    <>
      <PriceSection rows={s.prices} units={units} />

      <CostSection kind="rates" title="Dollar to rupee rate"
        about="OpenAI and LiveKit bill in dollars. Set the rate your card is actually charged; a new rate applies from its date on."
        rows={s.rates} addLabel="New rate from a date"
        fresh={() => ({ valid_from: today(), inr_per_usd: s.rates.at(-1)?.inr_per_usd ?? 95, note: "" })}
        fields={[
          { name: "inr_per_usd", label: "Rupees for one dollar", kind: "number" },
          { name: "valid_from", label: "From", kind: "date" },
          { name: "note", label: "Note", kind: "text", optional: true },
        ]}
        show={(r) => <><b className="tabular-nums">₹{r.inr_per_usd} = $1</b> <span className="text-muted-foreground">from {day(r.valid_from)}</span></>}
        note={(r) => r.note} />

      <CostSection kind="allowances" title="Free allowances"
        about="Free usage your plan includes each month. The month's total takes it off; each call still shows its full price."
        rows={s.allowances} addLabel="Add an allowance" units={units}
        fresh={() => ({ provider: "livekit", unit: "minutes", quantity: 0, valid_from: today(), note: "" })}
        fields={[
          { name: "provider", label: "Vendor", kind: "vendor" },
          { name: "unit", label: "Of what", kind: "unit" },
          { name: "quantity", label: "How much a month", kind: "number" },
          { name: "valid_from", label: "From", kind: "date" },
          { name: "note", label: "Note", kind: "text", optional: true },
        ]}
        show={(r) => <><b>{vendor(r.provider)}</b>: {quantity(r.quantity)} {units[r.unit] ?? r.unit} a month <span className="text-muted-foreground">from {day(r.valid_from)}</span></>}
        note={(r) => r.note} />

      <CostSection kind="fixed" title="Monthly fees"
        about="Plan subscriptions you pay whatever the usage (a LiveKit Ship plan, say)."
        rows={s.fixed} addLabel="Add a fee"
        fresh={() => ({ name: "", provider: "livekit", amount: 0, currency: "USD", valid_from: `${thisMonth()}-01`, valid_to: null })}
        fields={[
          { name: "name", label: "Name", kind: "text", hint: "e.g. LiveKit Ship plan" },
          { name: "provider", label: "Vendor", kind: "vendor" },
          { name: "amount", label: "A month", kind: "number" },
          { name: "currency", label: "Currency", kind: "currency" },
          { name: "valid_from", label: "First month", kind: "date" },
          { name: "valid_to", label: "Last month", kind: "date", optional: true, hint: "Blank while you still pay it." },
        ]}
        show={(r) => <><b>{r.name}</b> · {money(r.amount, r.currency)} a month <span className="text-muted-foreground">from {day(r.valid_from)}{r.valid_to ? ` to ${day(r.valid_to)}` : ""}</span></>} />

      <CostSection kind="bills" title="Vendors' bills"
        about="Type in what each vendor actually billed for a month (from its invoice or usage page). Costs compares it with ours."
        rows={s.bills} addLabel="Add a bill"
        fresh={() => ({ month: thisMonth(), provider: "sarvam", amount: 0, currency: "INR", note: "" })}
        fields={[
          { name: "month", label: "Month", kind: "month" },
          { name: "provider", label: "Vendor", kind: "vendor" },
          { name: "amount", label: "Amount billed", kind: "number" },
          { name: "currency", label: "Currency", kind: "currency" },
          { name: "note", label: "Note", kind: "text", optional: true },
        ]}
        show={(r) => <><b>{vendor(r.provider)}</b> · {monthName(r.month)}: <span className="tabular-nums">{money(r.amount, r.currency)}</span></>}
        note={(r) => r.note} />
    </>
  );
}
