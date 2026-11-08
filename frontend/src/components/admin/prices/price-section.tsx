"use client";
// Vendors' prices, one row per model. A language model's three token prices
// (input, cached, output) are one row and one form, saved together by the
// API; speech and call-minute prices are a row each. Dated: a new price
// applies from its day on, so past calls keep what they cost.
import { useState } from "react";
import { CalendarPlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { money, perText, useCostRow, useModelPrices, VENDORS } from "@/lib/costs";
import type { Schemas } from "@/lib/api/client";
import { RemoveDialog, RowButtons, SectionShell } from "./cost-section";
import { day, RowForm, today, type Field, type Units, type Values } from "./row-form";

type PriceRow = Schemas["PriceRow"];
const TOKENS = ["tokens_in", "tokens_cached", "tokens_out"] as const;
type TokenUnit = (typeof TOKENS)[number];
const MODEL = "model"; // the form's "Charged for" choice that means a language model's tokens
const TOKEN_LABEL: Record<TokenUnit, string> = { tokens_in: "Input", tokens_cached: "Cached input", tokens_out: "Output" };
const TOKEN_SHORT: Record<TokenUnit, string> = { tokens_in: "Input", tokens_cached: "Cached", tokens_out: "Output" }; // form labels fit half a row

type Item =
  | { kind: "one"; key: string; provider: string; name: string; row: PriceRow }
  | { kind: "model"; key: string; provider: string; name: string; currency: string; valid_from: string; note: string; rows: Partial<Record<TokenUnit, PriceRow>> };

const isToken = (unit: string): unit is TokenUnit => (TOKENS as readonly string[]).includes(unit);
const perMillion = (r: PriceRow) => (r.amount / r.per) * 1_000_000;

/** One row per model: token prices of the same model, currency and date join up. */
function items(rows: PriceRow[]): Item[] {
  const out: Item[] = [];
  const models = new Map<string, Extract<Item, { kind: "model" }>>();
  for (const r of rows) {
    if (!isToken(r.unit)) {
      out.push({ kind: "one", key: `one-${r.id}`, provider: r.provider, name: r.model, row: r });
      continue;
    }
    const key = [r.provider, r.model, r.currency, r.valid_from].join("|");
    let m = models.get(key);
    if (!m) {
      m = { kind: "model", key, provider: r.provider, name: r.model, currency: r.currency, valid_from: r.valid_from, note: r.note, rows: {} };
      models.set(key, m);
      out.push(m);
    }
    m.rows[r.unit] = r;
    if (!m.note && r.note) m.note = r.note;
  }
  const from = (i: Item) => (i.kind === "one" ? i.row.valid_from : i.valid_from);
  return out.sort((a, b) => a.provider.localeCompare(b.provider) || a.name.localeCompare(b.name) || from(a).localeCompare(from(b)));
}

const COMMON: Field[] = [
  { name: "provider", label: "Vendor", kind: "vendor" },
  { name: "model", label: "Model", kind: "text", optional: true, hint: "Exactly as the call's vendors show it, e.g. gpt-4.1-mini. Blank: any model." },
];
const MODEL_FIELDS: Field[] = [
  { name: "currency", label: "Currency", kind: "currency" },
  ...TOKENS.map((u): Field => ({ name: u, label: `${TOKEN_SHORT[u]} per 1M tokens`, kind: "number" })),
  { name: "valid_from", label: "From", kind: "date" },
  { name: "note", label: "Note", kind: "text", optional: true },
];
const ONE_FIELDS: Field[] = [
  { name: "amount", label: "Price", kind: "number" },
  { name: "currency", label: "Currency", kind: "currency" },
  { name: "per", label: "For how many", kind: "number", hint: "e.g. 3600 seconds (an hour), 10000 characters" },
  { name: "valid_from", label: "From", kind: "date" },
  { name: "note", label: "Note", kind: "text", optional: true },
];
const UNIT_FIELD: Field = { name: "unit", label: "Charged for", kind: "unit" };

type Editing = { title: string; body: Values; id?: number; replace?: number[]; fixedKind?: boolean };

export function PriceSection({ rows, units }: { rows: PriceRow[]; units: Units }) {
  const one = useCostRow("prices");
  const model = useModelPrices();
  const [editing, setEditing] = useState<Editing | null>(null);
  const [deleting, setDeleting] = useState<Item | null>(null);

  // Speech and minutes keep their own units; the three token units become one choice.
  const choices: Units = { [MODEL]: "Language model: input, cached and output tokens" };
  for (const [u, label] of Object.entries(units)) if (!isToken(u)) choices[u] = label;
  const fields = (fixedKind?: boolean) => (v: Values) =>
    [...COMMON, ...(fixedKind ? [] : [UNIT_FIELD]), ...(v.unit === MODEL ? MODEL_FIELDS : ONE_FIELDS)];

  const bodyOf = (i: Item, valid_from?: string): Values =>
    i.kind === "one"
      ? { ...i.row, id: undefined, valid_from: valid_from ?? i.row.valid_from, note: valid_from ? "" : i.row.note }
      : {
        provider: i.provider, model: i.name, unit: MODEL, currency: i.currency,
        valid_from: valid_from ?? i.valid_from, note: valid_from ? "" : i.note,
        ...Object.fromEntries(TOKENS.map((u) => [u, i.rows[u] ? perMillion(i.rows[u]) : ""])),
      };
  const idsOf = (i: Extract<Item, { kind: "model" }>) => TOKENS.flatMap((u) => (i.rows[u] ? [i.rows[u].id] : []));

  const save = (e: Editing, v: Values) => {
    const close = { onSuccess: () => setEditing(null) };
    if (v.unit === MODEL) {
      model.save.mutate({
        provider: v.provider as Schemas["ModelPricesIn"]["provider"], model: String(v.model ?? ""),
        currency: v.currency as Schemas["ModelPricesIn"]["currency"], valid_from: String(v.valid_from), note: String(v.note ?? ""),
        tokens_in: Number(v.tokens_in), tokens_cached: Number(v.tokens_cached), tokens_out: Number(v.tokens_out),
        replace: e.replace ?? [],
      }, close);
    } else {
      const body: Values = { ...v };
      delete body.id;
      one.save.mutate({ id: e.id, body: body as Schemas["PriceIn"] }, close);
    }
  };

  const groups = new Map<string, Item[]>();
  for (const i of items(rows)) {
    const g = VENDORS[i.provider] ?? i.provider;
    groups.set(g, [...(groups.get(g) ?? []), i]);
  }

  return (
    <SectionShell id="prices" title="Vendor prices" addLabel="Add a price"
      about="One row per model. Each price applies from its date on, so a vendor's new price never changes what past calls cost. A blank model covers every model of that vendor without its own price."
      onAdd={() => setEditing({
        title: "Add a price",
        body: { provider: "sarvam", model: "", unit: MODEL, currency: "INR", amount: 0, per: 3600, valid_from: today(), note: "" },
      })}>
      {groups.size ? [...groups.entries()].map(([g, list]) => (
        <div key={g}>
          <h3 className="bg-muted/50 px-5 py-1.5 text-xs font-semibold tracking-wider text-muted-foreground uppercase">{g}</h3>
          <ul className="divide-y">
            {list.map((i) => (
              <li key={i.key} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 px-5 py-3 text-sm">
                <div className="min-w-0 flex-1">
                  <span className="font-medium">{i.name || "Any model"}</span>
                  {i.kind === "one" ? (
                    <span className="block tabular-nums">
                      {money(i.row.amount, i.row.currency)} per {perText(i.row.per, i.row.unit, units)}{" "}
                      <span className="text-muted-foreground">from {day(i.row.valid_from)}</span>
                    </span>
                  ) : (
                    <span className="block tabular-nums">
                      {TOKENS.map((u, n) => (
                        <span key={u}>
                          {n > 0 && <span className="text-muted-foreground"> · </span>}
                          {TOKEN_LABEL[u]} {i.rows[u] ? money(perMillion(i.rows[u]), i.currency) : <span className="text-muted-foreground">no price</span>}
                        </span>
                      ))}{" "}
                      <span className="text-muted-foreground">per million tokens, from {day(i.valid_from)}</span>
                    </span>
                  )}
                  {(i.kind === "one" ? i.row.note : i.note) && (
                    <p className="text-xs text-muted-foreground">{i.kind === "one" ? i.row.note : i.note}</p>
                  )}
                </div>
                <RowButtons
                  onChange={() => setEditing({
                    title: "Change: vendor price", body: bodyOf(i), fixedKind: true,
                    ...(i.kind === "one" ? { id: i.row.id } : { replace: idsOf(i) }),
                  })}
                  onRemove={() => setDeleting(i)}>
                  <Button variant="ghost" size="sm" aria-label="New price from a date" title="The vendor changed this price: add the new one from a date"
                    onClick={() => setEditing({ title: "New price from a date", body: bodyOf(i, today()), fixedKind: true })}>
                    <CalendarPlus /> <span className="hidden sm:inline">New price</span>
                  </Button>
                </RowButtons>
              </li>
            ))}
          </ul>
        </div>
      )) : <p className="px-5 py-4 text-sm text-muted-foreground">None yet.</p>}

      {editing && (
        <RowForm title={editing.title} fields={fields(editing.fixedKind)} initial={editing.body} units={choices}
          pending={one.save.isPending || model.save.isPending}
          onCancel={() => setEditing(null)} onSave={(v) => save(editing, v)} />
      )}
      <RemoveDialog open={!!deleting} onKeep={() => setDeleting(null)}
        onRemove={() => {
          if (!deleting) return;
          if (deleting.kind === "one") one.remove.mutate(deleting.row.id);
          else model.remove.mutate(idsOf(deleting));
        }} />
    </SectionShell>
  );
}
