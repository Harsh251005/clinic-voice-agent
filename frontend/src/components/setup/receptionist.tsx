"use client";
// A clinic's Receptionist tab (admins only; Harsh, 2026-11-10): what this
// clinic adds to the shared rules, how to find it, its voice and its call
// length. The shared rules and settings are on Admin > Receptionist.
import { useState } from "react";
import Link from "next/link";
import { AlertCircle } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import type { Schemas } from "@/lib/api/client";
import { useClinicReceptionist, useSaveClinicReceptionist, type ClinicReceptionist } from "@/lib/clinic-receptionist";
import { words } from "@/lib/receptionist";
import { cn } from "@/lib/utils";
import { Field } from "./field";
import { Section } from "./section";
import { VoiceImpact } from "./voice-impact";

export function Receptionist({ clinic }: { clinic: Schemas["Clinic"] }) {
  const page = useClinicReceptionist(clinic.id);
  if (page.isError) return <Alert variant="destructive"><AlertCircle /><AlertDescription>{page.error.message}</AlertDescription></Alert>;
  if (!page.data) return <Skeleton className="h-96" />;
  return <Form key={JSON.stringify(page.data)} saved={page.data} />;
}

type Editable = Pick<ClinicReceptionist, "instructions" | "directions" | "tts_model" | "tts_speaker" | "tts_pace" | "tts_pitch" | "max_call_minutes">;

function Form({ saved }: { saved: ClinicReceptionist }) {
  const save = useSaveClinicReceptionist(saved.clinic_id);
  const start: Editable = {
    instructions: saved.instructions, directions: saved.directions, tts_model: saved.tts_model, tts_speaker: saved.tts_speaker,
    tts_pace: saved.tts_pace, tts_pitch: saved.tts_pitch, max_call_minutes: saved.max_call_minutes,
  };
  const [form, setForm] = useState(start);
  const set = (patch: Partial<Editable>) => setForm((f) => ({ ...f, ...patch }));
  const changed = Object.fromEntries(Object.entries(form).filter(([k, v]) => v !== start[k as keyof Editable]));
  const dirty = Object.keys(changed).length > 0;
  const count = words(form.instructions);
  const over = count > saved.instructions_max_words;
  const voiceChanged = form.tts_model !== start.tts_model || form.tts_speaker !== start.tts_speaker || form.tts_pitch !== start.tts_pitch;
  const limit = (name: string) => saved.limits[name];

  return (
    <form className="space-y-6" onSubmit={(e) => { e.preventDefault(); save.mutate(changed); }}>
      <p className="text-sm text-muted-foreground">
        Only admins see this tab. Rules every clinic shares are on <Link href="/admin/receptionist" className="underline underline-offset-2">Admin › Receptionist</Link>.
      </p>
      <Section title="This clinic's instructions"
        description="Added after the main rules on this clinic's calls. Short and plain: one instruction per line.">
        <Field id="instructions" label="Instructions"
          hint={<span className={cn("tabular-nums", over && "font-medium text-destructive")}>{count} of {saved.instructions_max_words} words. Every word is sent on every turn of every call, so keep it short.</span>}>
          <Textarea id="instructions" rows={5} aria-invalid={over} value={form.instructions}
            placeholder={"Tell callers parking is free behind the building.\nFor children under 5, suggest a morning slot."}
            onChange={(e) => set({ instructions: e.target.value })} />
        </Field>
      </Section>

      <Section title="Directions" description="What she says when a caller asks the way, instead of reading the postal address word for word.">
        <Field id="directions" label="How to find the clinic" hint={`${form.directions.length} of ${saved.directions_max_chars} characters.`}>
          <Textarea id="directions" rows={2} maxLength={saved.directions_max_chars} value={form.directions}
            placeholder="Near Borivali East station, opposite the HDFC bank, first floor."
            onChange={(e) => set({ directions: e.target.value })} />
        </Field>
      </Section>

      <Section title="Voice" description="How she sounds on this clinic's calls. The model and speaker are saved together: a speaker exists only in some models, and a pair that doesn't work is refused.">
        <div className="grid gap-4 md:grid-cols-2">
          <Field id="tts_model" label="Voice model" hint="A Sarvam voice model, e.g. bulbul:v3 or bulbul:v4-flash.">
            <Input id="tts_model" maxLength={100} value={form.tts_model} placeholder={`Blank: ${saved.model_default}`}
              onChange={(e) => set({ tts_model: e.target.value })} />
          </Field>
          <Field id="tts_speaker" label="Speaker" hint="A Sarvam voice name that this model has.">
            <Input id="tts_speaker" maxLength={50} value={form.tts_speaker} placeholder={`Blank: ${saved.speaker_default}`}
              onChange={(e) => set({ tts_speaker: e.target.value })} />
          </Field>
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <Field id="tts_pace" label="Speed" hint={`${limit("tts_pace").low}× to ${limit("tts_pace").high}×. Recorded lines keep their own speed.`}>
            <Input id="tts_pace" type="number" inputMode="decimal" step="0.05" required
              min={limit("tts_pace").low ?? undefined} max={limit("tts_pace").high ?? undefined} value={form.tts_pace}
              onChange={(e) => set({ tts_pace: Number(e.target.value) })} />
          </Field>
          <Field id="tts_pitch" label="Pitch" hint={`${limit("tts_pitch").low} to ${limit("tts_pitch").high}. Blank: the voice's own. Only some voice models apply it.`}>
            <Input id="tts_pitch" type="number" inputMode="decimal" step="0.05"
              min={limit("tts_pitch").low ?? undefined} max={limit("tts_pitch").high ?? undefined}
              value={form.tts_pitch ?? ""} placeholder="Blank"
              onChange={(e) => set({ tts_pitch: e.target.value === "" ? null : Number(e.target.value) })} />
          </Field>
        </div>
        {voiceChanged && <VoiceImpact clinicId={saved.clinic_id} model={form.tts_model} speaker={form.tts_speaker} pitch={form.tts_pitch} />}
      </Section>

      <Section title="Calls">
        <div className="max-w-xs">
          <Field id="max_call_minutes" label="Longest call (minutes)"
            hint={`Then she says the time-limit goodbye and hangs up. ${limit("max_call_minutes").low} to ${limit("max_call_minutes").high}.`}>
            <Input id="max_call_minutes" type="number" inputMode="decimal" step="1" required
              min={limit("max_call_minutes").low ?? undefined} max={limit("max_call_minutes").high ?? undefined}
              value={form.max_call_minutes} onChange={(e) => set({ max_call_minutes: Number(e.target.value) })} />
          </Field>
        </div>
      </Section>

      <div className="sticky bottom-24 z-10 flex justify-end gap-2 rounded-xl border bg-card/95 p-3 shadow-sm backdrop-blur md:bottom-4">
        {dirty && <Button type="button" variant="ghost" onClick={() => setForm(start)}>Discard changes</Button>}
        <Button type="submit" disabled={!dirty || over || save.isPending}>
          {save.isPending ? "Saving…" : over ? `Instructions over ${saved.instructions_max_words} words` : "Save"}
        </Button>
      </div>
    </form>
  );
}
