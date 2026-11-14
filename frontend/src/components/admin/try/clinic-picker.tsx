"use client";
// Which clinic's receptionist to try. Locked while a chat is on: a chat
// belongs to the clinic it started with.
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { Schemas } from "@/lib/api/client";

export function ClinicPicker({ clinics, value, onChange, disabled }: {
  clinics: Schemas["AdminClinic"][]; value: number | null; onChange: (id: number) => void; disabled: boolean;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor="try-clinic">Clinic</Label>
      <Select value={value === null ? "" : String(value)} onValueChange={(v) => onChange(Number(v))} disabled={disabled}>
        <SelectTrigger id="try-clinic" className="w-full sm:w-80"><SelectValue placeholder="Pick a clinic" /></SelectTrigger>
        <SelectContent>
          {clinics.map((c) => (
            <SelectItem key={c.id} value={String(c.id)}>{c.name}{!c.active && " (paused)"}</SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
