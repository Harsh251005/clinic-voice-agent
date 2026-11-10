"use client";
// A line's recording speed (Harsh, 2026-11-10): apart from the live voice's,
// so tuning one never un-records the other. A new speed is said live until
// the line is recorded again.
import { Gauge } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { speeds } from "@/lib/voice";

export function SpeedSelect({ id, value, min, max, label, disabled, onChange }: {
  id: string; value: number; min: number; max: number; label: string; disabled: boolean; onChange: (pace: number) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <label htmlFor={id} className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
        <Gauge className="size-4" aria-hidden /> Speed
      </label>
      <Select value={value.toFixed(2)} disabled={disabled} onValueChange={(v) => onChange(Number(v))}>
        <SelectTrigger id={id} size="sm" className="w-24 tabular-nums" aria-label={`Recording speed: ${label}`}><SelectValue /></SelectTrigger>
        <SelectContent>
          {speeds(value, min, max).map((s) => (
            <SelectItem key={s} value={s.toFixed(2)} className="tabular-nums">{s.toFixed(2)}×{s === 1 ? " (normal)" : ""}</SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
