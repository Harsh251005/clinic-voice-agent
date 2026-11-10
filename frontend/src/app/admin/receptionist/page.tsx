"use client";
// Admin > Receptionist: how every clinic's receptionist behaves (Harsh,
// 2026-11-10). The rules, her brain, her hearing, the voice model, turn-taking
// and the greeting. Each clinic's own settings (instructions, directions,
// voice, call length) are on that clinic's Receptionist tab. A call reads
// these when it starts: a change applies from the next call, no restart.
import { useState } from "react";
import { AlertCircle } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { PageHeader } from "@/components/app/page-header";
import { Field } from "@/components/setup/field";
import { Section } from "@/components/setup/section";
import { RulesEditor } from "@/components/admin/receptionist/rules-editor";
import {
  TIMINGS, editable, useReceptionist, useSaveReceptionist, words, type SystemSettings,
} from "@/lib/receptionist";

const BRAINS: Record<string, string> = { sarvam: "Sarvam", openai: "OpenAI" };

export default function ReceptionistPage() {
  const page = useReceptionist();
  return (
    <div className="space-y-6">
      <PageHeader title="Receptionist"
        description="How she behaves on every clinic's calls. Each clinic's own instructions, directions, voice and call length are on its Receptionist tab." />
      {page.isError ? (
        <Alert variant="destructive"><AlertCircle /><AlertDescription>{page.error.message}</AlertDescription></Alert>
      ) : !page.data ? (
        <div className="space-y-4"><Skeleton className="h-96" /><Skeleton className="h-48" /></div>
      ) : (
        <Form key={JSON.stringify(editable(page.data))} saved={page.data} />
      )}
    </div>
  );
}

function Form({ saved }: { saved: SystemSettings }) {
  const save = useSaveReceptionist();
  const start = editable(saved);
  const [form, setForm] = useState(start);
  const set = (patch: Partial<typeof form>) => setForm((f) => ({ ...f, ...patch }));
  const changed = Object.fromEntries(
    Object.entries(form).filter(([k, v]) => v !== start[k as keyof typeof start]),
  ) as Partial<typeof form>;
  const dirty = Object.keys(changed).length > 0;
  const tooLong = words(form.rules || saved.default_rules) > saved.rules_max_words;
  const blank = (key: string) => `Blank: ${saved.blank_means[key] ?? "the vendor's default"}`;

  const text = (key: "sarvam_llm_model" | "openai_llm_model" | "sarvam_stt_model" | "sarvam_stt_language" | "sarvam_stt_mode" | "sarvam_tts_model",
    label: string, hint?: string) => (
    <Field id={key} label={label} hint={hint}>
      <Input id={key} maxLength={100} value={form[key]} placeholder={blank(key)} onChange={(e) => set({ [key]: e.target.value })} />
    </Field>
  );

  return (
    <form className="space-y-6" onSubmit={(e) => { e.preventDefault(); save.mutate(changed); }}>
      <Section title="Main rules" description="What she is, how she talks and what she may do, for every clinic.">
        <RulesEditor value={form.rules} fallback={saved.default_rules} maxWords={saved.rules_max_words}
          onChange={(rules) => set({ rules })} />
      </Section>

      <Section title="Brain" description="The language model that writes her replies and uses the booking tools.">
        <div className="grid gap-4 md:grid-cols-3">
          <Field id="hindi_llm" label="Model vendor">
            <Select value={form.hindi_llm} onValueChange={(v) => set({ hindi_llm: v as typeof form.hindi_llm })}>
              <SelectTrigger id="hindi_llm" className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>
                {saved.llm_vendors.map((v) => <SelectItem key={v} value={v}>{BRAINS[v] ?? v}</SelectItem>)}
              </SelectContent>
            </Select>
          </Field>
          {text("sarvam_llm_model", "Sarvam model", form.hindi_llm === "sarvam" ? "In use." : "Used when the vendor is Sarvam.")}
          {text("openai_llm_model", "OpenAI model", form.hindi_llm === "openai" ? "In use." : "Used when the vendor is OpenAI.")}
        </div>
      </Section>

      <Section title="Hearing and voice model" description="Sarvam turns the caller's speech into text and speaks her replies. Each clinic picks its own speaker, speed and pitch.">
        <div className="grid gap-4 md:grid-cols-2">
          {text("sarvam_stt_model", "Speech-to-text model")}
          {text("sarvam_stt_language", "Language heard", "“unknown” detects it per sentence, so Hinglish comes through as said.")}
          {text("sarvam_stt_mode", "Speech-to-text mode", "How Sarvam writes down what it hears. Replies must stay in Devanagari, so avoid a romanised (translit) mode.")}
          {text("sarvam_tts_model", "Voice model", "Changing it leaves recorded lines said live until re-recorded.")}
        </div>
      </Section>

      <Section title="Turn-taking" description="When she decides the caller has finished, and when she stops for them.">
        <div className="grid gap-4 md:grid-cols-2">
          {TIMINGS.map(({ key, label, hint }) => {
            const limit = saved.limits[key];
            return (
              <Field key={key} id={key} label={label} hint={`${hint} Default ${limit.default}.`}>
                <Input id={key} type="number" inputMode="decimal" step="0.05" required
                  min={limit.low ?? undefined} max={limit.high ?? undefined} value={form[key]}
                  onChange={(e) => set({ [key]: Number(e.target.value) })} />
              </Field>
            );
          })}
        </div>
      </Section>

      <Section title="Greeting">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <label htmlFor="greeting_interruptible" className="text-sm font-medium">Callers can talk over the greeting</label>
            <p className="text-sm text-muted-foreground">
              Off: every caller hears the whole greeting first. On: she stops as soon as the caller speaks.
            </p>
          </div>
          <Switch id="greeting_interruptible" checked={form.greeting_interruptible}
            onCheckedChange={(on) => set({ greeting_interruptible: on })} />
        </div>
      </Section>

      <div className="sticky bottom-4 flex justify-end gap-2">
        {dirty && <Button type="button" variant="ghost" onClick={() => setForm(start)}>Discard changes</Button>}
        <Button type="submit" disabled={!dirty || tooLong || save.isPending}>
          {save.isPending ? "Saving…" : tooLong ? `Rules over ${saved.rules_max_words} words` : "Save"}
        </Button>
      </div>
    </form>
  );
}
