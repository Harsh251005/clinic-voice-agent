"use client";
// The form behind every row on the Prices page: a dialog of typed fields
// (text, number, date, month, vendor, unit, currency). The fields may follow
// what is typed (a language model's price asks for three amounts, not one).
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PRICED_VENDORS } from "@/lib/costs";

export type Units = Record<string, string>;
export type Values = Record<string, unknown>;
export type Field = {
  name: string;
  label: string;
  kind: "text" | "number" | "date" | "month" | "vendor" | "unit" | "currency";
  hint?: string;
  optional?: boolean;
};

export const today = () => new Date().toLocaleDateString("en-CA"); // YYYY-MM-DD, local
export const thisMonth = () => today().slice(0, 7);

/** "1 Oct 2026" from "2026-10-01", without a timezone shift. */
export function day(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

const PER: Record<string, number> = { seconds_heard: 3600, characters: 1000, minutes: 1 };
const CURRENCY: Record<string, string> = { sarvam: "INR", openai: "USD", livekit: "USD" };

export function RowForm({ title, fields, initial, units, pending, onCancel, onSave }: {
  title: string; fields: Field[] | ((v: Values) => Field[]); initial: Values; units: Units; pending: boolean;
  onCancel: () => void; onSave: (body: Values) => void;
}) {
  const [v, setV] = useState<Values>(initial);
  const shown = typeof fields === "function" ? fields(v) : fields;
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
          const body: Values = { ...v };
          for (const f of shown) {
            if (f.kind === "number") body[f.name] = Number(body[f.name]);
            if (f.optional && f.kind === "date" && !body[f.name]) body[f.name] = null;
          }
          onSave(body);
        }}>
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            <DialogDescription>Saved at once; every cost it covers is worked out again.</DialogDescription>
          </DialogHeader>
          <div className="my-4 grid gap-4 sm:grid-cols-2">
            {shown.map((f) => (
              <div key={f.name} className={f.kind === "text" || f.kind === "unit" ? "space-y-1.5 sm:col-span-2" : "space-y-1.5"}>
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
    case "vendor": return choose(Object.entries(PRICED_VENDORS));
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
