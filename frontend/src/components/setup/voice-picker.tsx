"use client";
// A clinic's voice, picked not typed (Harsh, 2026-11-12): voice model and
// voice from lists (women's voices only: she is always a woman), speed and
// pitch on sliders. Pitch shows only for a model that applies it.
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import type { ClinicReceptionist } from "@/lib/clinic-receptionist";
import { Field } from "./field";

export type Voice = Pick<ClinicReceptionist, "tts_model" | "tts_speaker" | "tts_pace" | "tts_pitch">;
type Limits = ClinicReceptionist["limits"];

const modelLabel = (name: string) => name.replace("bulbul:", "Bulbul ").replaceAll("-", " ");
const speedWord = (pace: number) => (pace < 0.95 ? "slower" : pace > 1.05 ? "faster" : "normal");
const pitchWord = (pitch: number) => (pitch < 0 ? "lower" : pitch > 0 ? "higher" : "her own");

export function VoicePicker({ voices, modelDefault, limits, value, onChange }: {
  voices: ClinicReceptionist["voices"]; modelDefault: string; limits: Limits;
  value: Voice; onChange: (patch: Partial<Voice>) => void;
}) {
  // Blank in the database means the default: show what a call would really use.
  const modelName = value.tts_model || modelDefault;
  const model = voices.find((m) => m.name === modelName);
  const speakerName = value.tts_speaker || model?.default_speaker || "";
  const speakers = model?.speakers ?? [];
  const pitch = value.tts_pitch ?? 0;

  const pickModel = (name: string) => {
    const next = voices.find((m) => m.name === name);
    if (!next) return;
    // Keep the same woman when the new model has her, and drop a pitch the new model ignores.
    const first = speakerName.split("_")[0];
    const same = next.speakers.find((s) => s.name.split("_")[0] === first);
    onChange({ tts_model: name, tts_speaker: (same ?? { name: next.default_speaker }).name, ...(next.pitch ? {} : { tts_pitch: null }) });
  };

  return (
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-2">
        <Field id="tts_model" label="Voice model" hint={model?.pitch ? "This model lets you set her pitch." : "This model has no pitch setting."}>
          <Select value={modelName} onValueChange={pickModel}>
            <SelectTrigger id="tts_model" className="w-full"><SelectValue /></SelectTrigger>
            <SelectContent>
              {!model && <SelectItem value={modelName}>{modelName} (not on the list)</SelectItem>}
              {voices.map((m) => <SelectItem key={m.name} value={m.name}>{modelLabel(m.name)}</SelectItem>)}
            </SelectContent>
          </Select>
        </Field>
        <Field id="tts_speaker" label="Voice" hint={`${speakers.length} women's voices in this model.`}>
          {/* After a reload the browser can make the list report an empty pick: never a real choice. */}
          <Select value={speakerName} onValueChange={(name) => { if (name) onChange({ tts_speaker: name }); }}>
            <SelectTrigger id="tts_speaker" className="w-full"><SelectValue /></SelectTrigger>
            <SelectContent className="max-h-72">
              {!speakers.some((s) => s.name === speakerName) && speakerName && (
                <SelectItem value={speakerName}>{speakerName} (not on the list)</SelectItem>
              )}
              {speakers.map((s) => <SelectItem key={s.name} value={s.name}>{s.label}</SelectItem>)}
            </SelectContent>
          </Select>
        </Field>
      </div>
      <div className="grid gap-x-4 gap-y-5 md:grid-cols-2">
        <Field id="tts_pace" label="Speed" hint="Recorded lines keep their own speed.">
          <Scale id="tts_pace" low={limits.tts_pace.low ?? 0.5} high={limits.tts_pace.high ?? 2} value={value.tts_pace}
            text={`${value.tts_pace.toFixed(2)}×, ${speedWord(value.tts_pace)}`} ends={["Slower", "Faster"]}
            onChange={(tts_pace) => onChange({ tts_pace })} />
        </Field>
        {model?.pitch && (
          <Field id="tts_pitch" label="Pitch" hint="In the middle she keeps the voice's own pitch.">
            <Scale id="tts_pitch" low={limits.tts_pitch.low ?? -0.5} high={limits.tts_pitch.high ?? 0.5} value={pitch}
              text={pitch === 0 ? "Her own" : `${pitch > 0 ? "+" : ""}${pitch.toFixed(2)}, ${pitchWord(pitch)}`} ends={["Lower", "Higher"]}
              onChange={(p) => onChange({ tts_pitch: p === 0 ? null : p })} />
          </Field>
        )}
      </div>
    </div>
  );
}

function Scale({ id, low, high, value, text, ends, onChange }: {
  id: string; low: number; high: number; value: number; text: string; ends: [string, string]; onChange: (value: number) => void;
}) {
  return (
    <div className="space-y-1.5 pt-1">
      <Slider id={id} min={low} max={high} step={0.05} value={value} aria-valuetext={text}
        onChange={(e) => onChange(Math.round(Number(e.target.value) * 100) / 100)} />
      <div className="flex items-baseline justify-between text-xs text-muted-foreground">
        <span>{ends[0]}</span>
        <output htmlFor={id} className="text-sm font-medium text-foreground tabular-nums">{text}</output>
        <span>{ends[1]}</span>
      </div>
    </div>
  );
}
