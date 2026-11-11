"use client";
// The "Name in Hindi" box. Nothing is written while staff type: the Hindi is
// asked for only when they click "Write in Hindi" (a suggestion from the API,
// from the English name), and it is theirs to change before saving.
import { useState } from "react";
import { Loader2, Languages } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, unwrap } from "@/lib/api/client";
import { Field } from "./field";

export function HindiNameField({ id, label, clinicId, english, value, onChange, placeholder }: {
  id: string; label: string; clinicId: number; english: string; value: string;
  onChange: (value: string) => void; placeholder: string;
}) {
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const [filled, setFilled] = useState<string | null>(null); // what the button last wrote, for the hint
  const name = english.trim();

  async function write() {
    setBusy(true);
    setFailed(false);
    try {
      const { name_hi } = await unwrap(api.POST("/api/clinics/{clinic_id}/hindi-name", {
        params: { path: { clinic_id: clinicId } }, body: { name },
      }));
      setFilled(name_hi);
      onChange(name_hi);
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  }

  const hint = busy ? "Writing it in Hindi…"
    : failed ? "No suggestion just now. Type it in Hindi, or try again."
    : value && value === filled ? "Written from the English name. Change it if it doesn't sound right."
    : "How the receptionist says it on Hindi calls. Click “Write in Hindi” to fill it from the English name.";
  return (
    <Field id={id} label={label} hint={hint}>
      <div className="flex gap-2">
        <Input id={id} lang="hi" maxLength={200} placeholder={placeholder} value={value}
          onChange={(e) => onChange(e.target.value)} />
        <Button type="button" variant="outline" disabled={!name || busy} onClick={write}>
          {busy ? <Loader2 className="animate-spin" aria-hidden /> : <Languages aria-hidden />} Write in Hindi
        </Button>
      </div>
    </Field>
  );
}
