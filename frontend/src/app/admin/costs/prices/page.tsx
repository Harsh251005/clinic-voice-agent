"use client";
// Prices: everything the costs are worked out from, edited here and never in
// code. Vendors' prices (dated, so the past keeps its own), the dollar rate,
// free allowances, monthly fees, and each month's real bills to check against.
import { useState, type ReactNode } from "react";
import Link from "next/link";
import { AlertCircle, ArrowLeft, CalendarPlus, Pencil, Plus, Trash2 } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/app/page-header";
import { money, monthName, perText, quantity, useCostRow, useCostSettings, VENDORS, type CostKind } from "@/lib/costs";
import type { Schemas } from "@/lib/api/client";

type Units = Record<string, string>;
type Row = { id: number } & Record<string, unknown>;
type Field = {
  name: string;
  label: string;
  kind: "text" | "number" | "date" | "month" | "vendor" | "unit" | "currency";
  hint?: string;
  optional?: boolean;
};

const today = () => new Date().toLocaleDateString("en-CA"); // YYYY-MM-DD, local
const thisMonth = () => today().slice(0, 7);
const PER: Record<string, number> = { tokens_in: 1_000_000, tokens_cached: 1_000_000, tokens_out: 1_000_000, seconds_heard: 3600, characters: 1000, minutes: 1 };
const CURRENCY: Record<string, string> = { sarvam: "INR", elevenlabs: "USD", openai: "USD", livekit: "USD" };

function day(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

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

function Body({ s }: { s: Schemas["CostSettings"] }) {
  const units = s.units;
  return (
    <>
      <Section<"rates"> kind="rates" title="Dollar to rupee rate"
        about="OpenAI, ElevenLabs and LiveKit bill in dollars. Set the rate your card is actually charged; a new rate applies from its date on."
        rows={s.rates} addLabel="New rate from a date"
        fresh={() => ({ valid_from: today(), inr_per_usd: s.rates.at(-1)?.inr_per_usd ?? 95, note: "" })}
        fields={[
          { name: "inr_per_usd", label: "Rupees for one dollar", kind: "number" },
          { name: "valid_from", label: "From", kind: "date" },
          { name: "note", label: "Note", kind: "text", optional: true },
        ]}
        show={(r) => <><b className="tabular-nums">₹{r.inr_per_usd} = $1</b> <span className="text-muted-foreground">from {day(r.valid_from)}</span></>}
        note={(r) => r.note} />

      <Section<"prices"> kind="prices" title="Vendor prices"
        about="Each price applies from its date on, so a vendor's new price never changes what past calls cost. A blank model covers every model of that vendor without its own price."
        rows={s.prices} addLabel="Add a price" again units={units}
        fresh={() => ({ provider: "openai", model: "", unit: "tokens_in", amount: 0, per: PER.tokens_in, currency: "USD", valid_from: today(), note: "" })}
        fields={[
          { name: "provider", label: "Vendor", kind: "vendor" },
          { name: "model", label: "Model", kind: "text", optional: true, hint: "Exactly as the call's vendors show it, e.g. gpt-4.1-mini. Blank: any model." },
          { name: "unit", label: "Charged for", kind: "unit" },
          { name: "amount", label: "Price", kind: "number" },
          { name: "currency", label: "Currency", kind: "currency" },
          { name: "per", label: "For how many", kind: "number", hint: "e.g. 1000000 tokens, 3600 seconds (an hour), 1000 characters" },
          { name: "valid_from", label: "From", kind: "date" },
          { name: "note", label: "Note", kind: "text", optional: true },
        ]}
        group={(r) => VENDORS[r.provider] ?? r.provider}
        show={(r) => (
          <>
            <span className="font-medium">{r.model || "Any model"}</span>{" "}
            <span className="block tabular-nums">{money(r.amount, r.currency)} per {perText(r.per, r.unit, units)} <span className="text-muted-foreground">from {day(r.valid_from)}</span></span>
          </>
        )}
        note={(r) => r.note} />

      <Section<"allowances"> kind="allowances" title="Free allowances"
        about="Free usage your plan includes each month. The month's total takes it off; each call still shows its full price."
        rows={s.allowances} addLabel="Add an allowance" units={units}
        fresh={() => ({ provider: "elevenlabs", unit: "characters", quantity: 0, valid_from: today(), note: "" })}
        fields={[
          { name: "provider", label: "Vendor", kind: "vendor" },
          { name: "unit", label: "Of what", kind: "unit" },
          { name: "quantity", label: "How much a month", kind: "number" },
          { name: "valid_from", label: "From", kind: "date" },
          { name: "note", label: "Note", kind: "text", optional: true },
        ]}
        show={(r) => <><b>{VENDORS[r.provider] ?? r.provider}</b>: {quantity(r.quantity)} {units[r.unit] ?? r.unit} a month <span className="text-muted-foreground">from {day(r.valid_from)}</span></>}
        note={(r) => r.note} />

      <Section<"fixed"> kind="fixed" title="Monthly fees"
        about="Plan subscriptions you pay whatever the usage (an ElevenLabs Starter plan, a LiveKit Ship plan)."
        rows={s.fixed} addLabel="Add a fee"
        fresh={() => ({ name: "", provider: "elevenlabs", amount: 0, currency: "USD", valid_from: `${thisMonth()}-01`, valid_to: null })}
        fields={[
          { name: "name", label: "Name", kind: "text", hint: "e.g. ElevenLabs Starter plan" },
          { name: "provider", label: "Vendor", kind: "vendor" },
          { name: "amount", label: "A month", kind: "number" },
          { name: "currency", label: "Currency", kind: "currency" },
          { name: "valid_from", label: "First month", kind: "date" },
          { name: "valid_to", label: "Last month", kind: "date", optional: true, hint: "Blank while you still pay it." },
        ]}
        show={(r) => <><b>{r.name}</b> · {money(r.amount, r.currency)} a month <span className="text-muted-foreground">from {day(r.valid_from)}{r.valid_to ? ` to ${day(r.valid_to)}` : ""}</span></>} />

      <Section<"bills"> kind="bills" title="Vendors' bills"
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
        show={(r) => <><b>{VENDORS[r.provider] ?? r.provider}</b> · {monthName(r.month)}: <span className="tabular-nums">{money(r.amount, r.currency)}</span></>}
        note={(r) => r.note} />
    </>
  );
}

type RowOf = {
  rates: Schemas["RateRow"]; prices: Schemas["PriceRow"]; allowances: Schemas["AllowanceRow"];
  fixed: Schemas["FixedRow"]; bills: Schemas["BillRow"];
};
type BodyOf = {
  rates: Schemas["RateIn"]; prices: Schemas["PriceIn"]; allowances: Schemas["AllowanceIn"];
  fixed: Schemas["FixedIn"]; bills: Schemas["BillIn"];
};

function Section<K extends CostKind>({ kind, title, about, rows, fields, fresh, show, note, group, addLabel, again, units }: {
  kind: K; title: string; about: string; rows: RowOf[K][]; fields: Field[]; fresh: () => BodyOf[K];
  show: (r: RowOf[K]) => ReactNode; note?: (r: RowOf[K]) => string | null | undefined;
  group?: (r: RowOf[K]) => string; addLabel: string; again?: boolean; units?: Units;
}) {
  const { save, remove } = useCostRow(kind);
  const [editing, setEditing] = useState<{ id?: number; title: string; body: BodyOf[K] } | null>(null);
  const [deleting, setDeleting] = useState<RowOf[K] | null>(null);
  const bodyOf = (r: RowOf[K]) => {
    const rest: Record<string, unknown> = { ...(r as unknown as Row) };
    delete rest.id;
    return rest as unknown as BodyOf[K];
  };

  const groups = new Map<string, RowOf[K][]>();
  for (const r of rows) {
    const g = group ? group(r) : "";
    groups.set(g, [...(groups.get(g) ?? []), r]);
  }

  return (
    <section aria-labelledby={`h-${kind}`} className="rounded-xl border bg-card">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b px-5 py-3.5">
        <div className="max-w-2xl">
          <h2 id={`h-${kind}`} className="font-semibold">{title}</h2>
          <p className="text-sm text-muted-foreground">{about}</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => setEditing({ title: addLabel, body: fresh() })}><Plus /> {addLabel}</Button>
      </div>
      {rows.length ? (
        [...groups.entries()].map(([g, list]) => (
          <div key={g}>
            {g && <h3 className="bg-muted/50 px-5 py-1.5 text-xs font-semibold tracking-wider text-muted-foreground uppercase">{g}</h3>}
            <ul className="divide-y">
              {list.map((r) => (
                <li key={r.id} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 px-5 py-3 text-sm">
                  <div className="min-w-0 flex-1">
                    {show(r)}
                    {note?.(r) && <p className="text-xs text-muted-foreground">{note(r)}</p>}
                  </div>
                  <div className="flex gap-1">
                    {again && (
                      <Button variant="ghost" size="sm" aria-label="New price from a date" title="The vendor changed this price: add the new one from a date"
                        onClick={() => setEditing({ title: "New price from a date", body: { ...bodyOf(r), valid_from: today(), note: "" } })}>
                        <CalendarPlus /> <span className="hidden sm:inline">New price</span>
                      </Button>
                    )}
                    <Button variant="ghost" size="icon" aria-label="Change" title="Change (fix a mistake)"
                      onClick={() => setEditing({ id: r.id, title: `Change: ${title.toLowerCase()}`, body: bodyOf(r) })}><Pencil /></Button>
                    <Button variant="ghost" size="icon" aria-label="Remove" title="Remove" onClick={() => setDeleting(r)}><Trash2 /></Button>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ))
      ) : <p className="px-5 py-4 text-sm text-muted-foreground">None yet.</p>}

      {editing && (
        <RowForm title={editing.title} fields={fields} initial={editing.body} units={units ?? {}} pending={save.isPending}
          onCancel={() => setEditing(null)}
          onSave={(body) => save.mutate({ id: editing.id, body }, { onSuccess: () => setEditing(null) })} />
      )}
      <AlertDialog open={!!deleting} onOpenChange={(o) => !o && setDeleting(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove this?</AlertDialogTitle>
            <AlertDialogDescription>Costs are worked out again without it. Calls it priced may show as incomplete.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep it</AlertDialogCancel>
            <AlertDialogAction onClick={() => deleting && remove.mutate(deleting.id)}>Remove</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}

function RowForm<B>({ title, fields, initial, units, pending, onCancel, onSave }: {
  title: string; fields: Field[]; initial: B; units: Units; pending: boolean; onCancel: () => void; onSave: (body: B) => void;
}) {
  const [v, setV] = useState<Record<string, unknown>>(initial as Record<string, unknown>);
  const set = (name: string, value: unknown) => setV((old) => {
    const next = { ...old, [name]: value };
    // Prefill what follows from a choice: a vendor's own currency, a unit's usual "per".
    if (name === "provider" && "currency" in next && typeof value === "string") next.currency = CURRENCY[value] ?? next.currency;
    if (name === "unit" && "per" in next && typeof value === "string") {
      next.per = value === "characters" && next.provider === "sarvam" ? 10_000 : PER[value] ?? next.per;
    }
    return next;
  });

  return (
    <Dialog open onOpenChange={(o) => !o && onCancel()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <form onSubmit={(e) => {
          e.preventDefault();
          const body: Record<string, unknown> = { ...v };
          for (const f of fields) {
            if (f.kind === "number") body[f.name] = Number(body[f.name]);
            if (f.optional && f.kind === "date" && !body[f.name]) body[f.name] = null;
          }
          onSave(body as B);
        }}>
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            <DialogDescription>Saved at once; every cost it covers is worked out again.</DialogDescription>
          </DialogHeader>
          <div className="my-4 grid gap-4 sm:grid-cols-2">
            {fields.map((f) => (
              <div key={f.name} className={f.kind === "text" ? "space-y-1.5 sm:col-span-2" : "space-y-1.5"}>
                <Label htmlFor={`f-${f.name}`}>{f.label}{f.optional && <span className="font-normal text-muted-foreground"> (optional)</span>}</Label>
                <FieldInput f={f} value={v[f.name]} units={units} onChange={(x) => set(f.name, x)} />
                {f.hint && <p className="text-xs text-muted-foreground">{f.hint}</p>}
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onCancel}>Cancel</Button>
            <Button type="submit" disabled={pending}>{pending ? "Saving…" : "Save"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function FieldInput({ f, value, units, onChange }: { f: Field; value: unknown; units: Units; onChange: (v: unknown) => void }) {
  const id = `f-${f.name}`;
  const choose = (options: [string, string][]) => (
    <Select value={String(value ?? "")} onValueChange={onChange}>
      <SelectTrigger id={id} className="w-full"><SelectValue /></SelectTrigger>
      <SelectContent>{options.map(([k, label]) => <SelectItem key={k} value={k}>{label}</SelectItem>)}</SelectContent>
    </Select>
  );
  switch (f.kind) {
    case "vendor": return choose(Object.entries(VENDORS));
    case "unit": return choose(Object.entries(units));
    case "currency": return choose([["INR", "Rupees (₹)"], ["USD", "Dollars ($)"]]);
    case "number":
      return <Input id={id} type="number" inputMode="decimal" step="any" min={0} required value={String(value ?? "")} onChange={(e) => onChange(e.target.value)} />;
    case "date":
      return <Input id={id} type="date" required={!f.optional} value={String(value ?? "")} onChange={(e) => onChange(e.target.value)} />;
    case "month":
      return <Input id={id} type="month" required value={String(value ?? "")} onChange={(e) => onChange(e.target.value)} />;
    default:
      return <Input id={id} required={!f.optional} value={String(value ?? "")} onChange={(e) => onChange(e.target.value)} />;
  }
}
