"use client";
// One clinic's receptionist, on the admin's page for that clinic (Harsh,
// 2026-11-12: everything that differs per clinic in one place, simple enough
// for someone non-technical): her voice, what else she should know, and how
// calls run. What every clinic shares is on Admin > Receptionist.
import { useState } from "react";
import { AlertCircle } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { Field } from "@/components/setup/field";
import { Section } from "@/components/setup/section";
import { useClinicReceptionist, useSaveClinicReceptionist, type ClinicReceptionist } from "@/lib/clinic-receptionist";
import { words } from "@/lib/receptionist";
import { cn } from "@/lib/utils";
import { VoiceImpact } from "./voice-impact";
import { VoicePicker } from "./voice-picker";

export function Receptionist({ clinicId }: { clinicId: number }) {
  const page = useClinicReceptionist(clinicId);
  if (page.isError) return <Alert variant="destructive"><AlertCircle /><AlertDescription>{page.error.message}</AlertDescription></Alert>;
  if (!page.data) return <Skeleton className="h-96" />;
  return <Form key={JSON.stringify(page.data)} saved={page.data} />;
}

type Editable = Pick<ClinicReceptionist,
  "instructions" | "tts_model" | "tts_speaker" | "tts_pace" | "tts_pitch" | "max_call_minutes" | "slots_offered">;

const CALL_LENGTHS = [3, 5, 10, 15, 20, 30];
/** The usual choices within what is allowed, plus the saved one if it is unusual. */
function choices(usual: number[], saved: number, low: number, high: number): number[] {
  return [...new Set([...usual.filter((n) => n >= low && n <= high), saved])].sort((a, b) => a - b);
}

function Form({ saved }: { saved: ClinicReceptionist }) {
  const save = useSaveClinicReceptionist(saved.clinic_id);
  const start: Editable = {
    instructions: saved.instructions, tts_model: saved.tts_model, tts_speaker: saved.tts_speaker,
    tts_pace: saved.tts_pace, tts_pitch: saved.tts_pitch, max_call_minutes: saved.max_call_minutes, slots_offered: saved.slots_offered,
  };
  const [form, setForm] = useState(start);
  const set = (patch: Partial<Editable>) => setForm((f) => ({ ...f, ...patch }));
  const changed = Object.fromEntries(Object.entries(form).filter(([k, v]) => v !== start[k as keyof Editable]));
  const dirty = Object.keys(changed).length > 0;
  const count = words(form.instructions);
  const over = count > saved.instructions_max_words;
  const voiceChanged = form.tts_model !== start.tts_model || form.tts_speaker !== start.tts_speaker || form.tts_pitch !== start.tts_pitch;
  const minutes = saved.limits.max_call_minutes;
  const offered = saved.limits.slots_offered;

  return (
    <form className="space-y-6" onSubmit={(e) => { e.preventDefault(); save.mutate(changed); }}>
      <Section title="Her voice" description="How she sounds on this clinic's calls. Pick a voice model, then one of its voices.">
        <VoicePicker voices={saved.voices} modelDefault={saved.model_default} limits={saved.limits} value={form} onChange={set} />
        {voiceChanged && <VoiceImpact clinicId={saved.clinic_id} model={form.tts_model} speaker={form.tts_speaker} pitch={form.tts_pitch} />}
      </Section>

      <Section title="Extra instructions"
        description="Anything she should do on this clinic's calls on top of the rules every clinic shares. Leave it empty if there is nothing special.">
        <Field id="instructions" label="Instructions"
          hint={<span className={cn("tabular-nums", over && "font-medium text-destructive")}>{count} of {saved.instructions_max_words} words. One per line, short and plain.</span>}>
          <Textarea id="instructions" rows={4} aria-invalid={over} value={form.instructions}
            placeholder={"Tell callers parking is free behind the building.\nFor children under 5, suggest a morning slot."}
            onChange={(e) => set({ instructions: e.target.value })} />
        </Field>
      </Section>

      <Section title="On a call">
        <div className="grid gap-4 md:grid-cols-2">
          <Field id="max_call_minutes" label="Longest call" hint="Then she says the time-limit goodbye and hangs up.">
            <Select value={String(form.max_call_minutes)} onValueChange={(v) => { if (v) set({ max_call_minutes: Number(v) }); }}>
              <SelectTrigger id="max_call_minutes" className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>
                {choices(CALL_LENGTHS, form.max_call_minutes, minutes.low ?? 1, minutes.high ?? 60).map((n) => (
                  <SelectItem key={n} value={String(n)}>{n} minute{n === 1 ? "" : "s"}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <Field id="slots_offered" label="Free times she offers at once" hint="How many she reads out before asking which suits. More means a longer sentence.">
            <Select value={String(form.slots_offered)} onValueChange={(v) => { if (v) set({ slots_offered: Number(v) }); }}>
              <SelectTrigger id="slots_offered" className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>
                {choices([1, 2, 3, 4, 5, 6], form.slots_offered, offered.low ?? 1, offered.high ?? 6).map((n) => (
                  <SelectItem key={n} value={String(n)}>{n} time{n === 1 ? "" : "s"}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
        </div>
      </Section>

      {dirty && (
        <div className="sticky bottom-24 z-10 flex items-center justify-end gap-2 rounded-xl border bg-card/95 p-3 shadow-sm backdrop-blur md:bottom-4">
          <p className="mr-auto pl-1 text-sm text-muted-foreground">You have unsaved changes.</p>
          <Button type="button" variant="ghost" onClick={() => setForm(start)}>Discard</Button>
          <Button type="submit" disabled={over || save.isPending}>
            {save.isPending ? "Saving…" : over ? `Instructions over ${saved.instructions_max_words} words` : "Save"}
          </Button>
        </div>
      )}
    </form>
  );
}
