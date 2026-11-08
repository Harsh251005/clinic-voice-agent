"use client";
// One editable list on the Prices page (the dollar rate, free allowances,
// monthly fees, vendors' bills): its rows, add, change, remove. The shell and
// the remove dialog are shared with the vendor prices list.
import { useState, type ReactNode } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { useCostRow, type CostKind } from "@/lib/costs";
import type { Schemas } from "@/lib/api/client";
import { RowForm, type Field, type Units, type Values } from "./row-form";

type RowOf = {
  rates: Schemas["RateRow"]; prices: Schemas["PriceRow"]; allowances: Schemas["AllowanceRow"];
  fixed: Schemas["FixedRow"]; bills: Schemas["BillRow"];
};
type BodyOf = {
  rates: Schemas["RateIn"]; prices: Schemas["PriceIn"]; allowances: Schemas["AllowanceIn"];
  fixed: Schemas["FixedIn"]; bills: Schemas["BillIn"];
};

export function SectionShell({ id, title, about, addLabel, onAdd, children }: {
  id: string; title: string; about: string; addLabel: string; onAdd: () => void; children: ReactNode;
}) {
  return (
    <section aria-labelledby={`h-${id}`} className="rounded-xl border bg-card">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b px-5 py-3.5">
        <div className="max-w-2xl">
          <h2 id={`h-${id}`} className="font-semibold">{title}</h2>
          <p className="text-sm text-muted-foreground">{about}</p>
        </div>
        <Button variant="outline" size="sm" onClick={onAdd}><Plus /> {addLabel}</Button>
      </div>
      {children}
    </section>
  );
}

export function RemoveDialog({ open, onKeep, onRemove }: { open: boolean; onKeep: () => void; onRemove: () => void }) {
  return (
    <AlertDialog open={open} onOpenChange={(o) => !o && onKeep()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Remove this?</AlertDialogTitle>
          <AlertDialogDescription>Costs are worked out again without it. Calls it priced may show as incomplete.</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Keep it</AlertDialogCancel>
          <AlertDialogAction onClick={onRemove}>Remove</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export function RowButtons({ children, onChange, onRemove }: { children?: ReactNode; onChange: () => void; onRemove: () => void }) {
  return (
    <div className="flex gap-1">
      {children}
      <Button variant="ghost" size="icon" aria-label="Change" title="Change (fix a mistake)" onClick={onChange}><Pencil /></Button>
      <Button variant="ghost" size="icon" aria-label="Remove" title="Remove" onClick={onRemove}><Trash2 /></Button>
    </div>
  );
}

export function CostSection<K extends Exclude<CostKind, "prices">>({ kind, title, about, rows, fields, fresh, show, note, addLabel, units }: {
  kind: K; title: string; about: string; rows: RowOf[K][]; fields: Field[]; fresh: () => BodyOf[K];
  show: (r: RowOf[K]) => ReactNode; note?: (r: RowOf[K]) => string | null | undefined; addLabel: string; units?: Units;
}) {
  const { save, remove } = useCostRow(kind);
  const [editing, setEditing] = useState<{ id?: number; title: string; body: Values } | null>(null);
  const [deleting, setDeleting] = useState<RowOf[K] | null>(null);
  const bodyOf = (r: RowOf[K]): Values => {
    const rest: Values = { ...r };
    delete rest.id;
    return rest;
  };

  return (
    <SectionShell id={kind} title={title} about={about} addLabel={addLabel} onAdd={() => setEditing({ title: addLabel, body: { ...fresh() } })}>
      {rows.length ? (
        <ul className="divide-y">
          {rows.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 px-5 py-3 text-sm">
              <div className="min-w-0 flex-1">
                {show(r)}
                {note?.(r) && <p className="text-xs text-muted-foreground">{note(r)}</p>}
              </div>
              <RowButtons
                onChange={() => setEditing({ id: r.id, title: `Change: ${title.toLowerCase()}`, body: bodyOf(r) })}
                onRemove={() => setDeleting(r)} />
            </li>
          ))}
        </ul>
      ) : <p className="px-5 py-4 text-sm text-muted-foreground">None yet.</p>}

      {editing && (
        <RowForm title={editing.title} fields={fields} initial={editing.body} units={units ?? {}} pending={save.isPending}
          onCancel={() => setEditing(null)}
          onSave={(body) => save.mutate({ id: editing.id, body: body as BodyOf[K] }, { onSuccess: () => setEditing(null) })} />
      )}
      <RemoveDialog open={!!deleting} onKeep={() => setDeleting(null)} onRemove={() => deleting && remove.mutate(deleting.id)} />
    </SectionShell>
  );
}
