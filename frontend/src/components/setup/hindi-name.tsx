"use client";
// The "Name in Hindi" box: filled in from the English name as staff type
// (a suggestion from the API), and theirs to change. Their own edits are
// never overwritten; clearing the box asks for a fresh suggestion.
import { useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { api, unwrap } from "@/lib/api/client";
import { Field } from "./field";

const PAUSE_MS = 700; // after the last keystroke in the English name

export function HindiNameField({ id, label, clinicId, english, value, onChange, placeholder }: {
  id: string; label: string; clinicId: number; english: string; value: string;
  onChange: (value: string) => void; placeholder: string;
}) {
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const suggested = useRef<string | null>(null); // what we last filled in, to tell it from staff's own
  const [shown, setShown] = useState<string | null>(null); // the same, for the hint
  const latest = useRef({ value, onChange });
  useEffect(() => { latest.current = { value, onChange }; }); // the newest, for the timer below

  useEffect(() => {
    const name = english.trim();
    const { value: current } = latest.current;
    const ours = current === "" || current === suggested.current;
    if (!name || !ours) return;
    let stale = false;
    const timer = setTimeout(async () => {
      setBusy(true);
      setFailed(false);
      try {
        const { name_hi } = await unwrap(api.POST("/api/clinics/{clinic_id}/hindi-name", {
          params: { path: { clinic_id: clinicId } }, body: { name },
        }));
        const now = latest.current.value;
        if (!stale && (now === "" || now === suggested.current)) {
          suggested.current = name_hi;
          setShown(name_hi);
          latest.current.onChange(name_hi);
        }
      } catch {
        if (!stale) setFailed(true);
      } finally {
        if (!stale) setBusy(false);
      }
    }, PAUSE_MS);
    return () => { stale = true; clearTimeout(timer); };
  }, [english, clinicId, value === ""]); // eslint-disable-line react-hooks/exhaustive-deps

  const hint = busy ? "Writing it in Hindi…"
    : failed ? "No suggestion just now. Type it in Hindi, or leave it blank."
    : value && value === shown ? "Filled in from the English name. Change it if it doesn't sound right."
    : "How the receptionist says it on Hindi calls.";
  return (
    <Field id={id} label={label} hint={hint}>
      <div className="relative">
        <Input id={id} lang="hi" maxLength={200} placeholder={placeholder} value={value}
          onChange={(e) => onChange(e.target.value)} className="pr-9" />
        {busy && <Loader2 className="absolute top-1/2 right-3 size-4 -translate-y-1/2 animate-spin text-muted-foreground" aria-hidden />}
      </div>
    </Field>
  );
}
