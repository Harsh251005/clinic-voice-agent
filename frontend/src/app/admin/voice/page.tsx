"use client";
// Voice & phrases: the receptionist's fixed lines (greeting, "one moment",
// goodbyes), written in English with the Hindi she says, and their
// recordings in the current voice. Nothing records by itself: a line is
// recorded when you click Record, and is said live until then.
import { useState } from "react";
import { AlertCircle, AudioLines, Mic } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/app/page-header";
import { ClinicGreetings } from "@/components/admin/voice/clinic-greetings";
import { EditDialog, type Editing } from "@/components/admin/voice/edit-dialog";
import { PhraseCard } from "@/components/admin/voice/phrase-card";
import { RecordDialog, type Asked } from "@/components/admin/voice/record-dialog";
import {
  KINDS, ORDER, estimate, lines, missing, refOf, useVoiceChanges, useVoicePage, voiceName,
  type Phrase, type Take, type VoicePage,
} from "@/lib/voice";

export default function VoicePhrasesPage() {
  const page = useVoicePage();
  return (
    <div className="space-y-6">
      <PageHeader title="Voice & phrases"
        description="The lines she always says the same way. Recorded lines play instantly and cost nothing per call; the rest are said live." />
      {page.isError ? (
        <Alert variant="destructive"><AlertCircle /><AlertDescription>{page.error.message}</AlertDescription></Alert>
      ) : !page.data ? (
        <div className="space-y-4"><Skeleton className="h-28" /><Skeleton className="h-72" /></div>
      ) : (
        <Body page={page.data} />
      )}
    </div>
  );
}

function Body({ page }: { page: VoicePage }) {
  const change = useVoiceChanges();
  const [editing, setEditing] = useState<Editing | null>(null);
  const [asked, setAsked] = useState<Asked | null>(null);
  const canRecord = !!page.voice && !change.record.isPending;

  const ask = (title: string, phrase: Phrase, takes: Take[]) =>
    setAsked({ title, takes: takes.map((t) => ({ ref: refOf(phrase, t), spoken: t.spoken, again: !!t.recorded_at })) });

  const edit = (phrase: Phrase, label: string) => setEditing({
    title: `Change: ${label}`, source: phrase.source, text: phrase.text,
    greeting: phrase.kind !== "greeting" ? null : phrase.clinic_id ? "own" : "shared",
    clinicId: phrase.clinic_id ?? undefined,
    save: (body, done, failed) => phrase.kind === "greeting" && phrase.clinic_id
      ? change.ownGreeting.mutate({ clinicId: phrase.clinic_id, body }, { onSuccess: done, onError: (e) => failed(e.message) })
      : change.editPhrase.mutate({ id: phrase.id, body }, { onSuccess: done, onError: (e) => failed(e.message) }),
  });

  const ownGreeting = (clinicId: number) => {
    const shared = page.phrases.find((p) => p.kind === "greeting" && p.clinic_id == null);
    const clinic = page.clinics.find((c) => c.id === clinicId);
    setEditing({
      title: `${clinic?.name ?? "This clinic"}: its own greeting`,
      source: shared?.source ?? "", text: (shared?.text ?? "").replaceAll("{clinic}", clinic?.spoken_name ?? ""),
      greeting: "own", clinicId,
      save: (body, done, failed) => change.ownGreeting.mutate({ clinicId, body }, { onSuccess: done, onError: (e) => failed(e.message) }),
    });
  };

  const todo = missing(page);
  const allTakes = page.phrases.flatMap((p) => p.takes.filter((t) => t.key));
  const recorded = allTakes.filter((t) => t.recorded_at).length;
  const todoChars = todo.reduce((n, t) => n + t.take.spoken.length, 0);

  return (
    <>
      <section aria-labelledby="h-voice" className="flex flex-wrap items-center gap-4 rounded-xl border bg-card px-5 py-4">
        <span className="grid size-10 place-items-center rounded-lg bg-muted text-muted-foreground"><AudioLines className="size-5" aria-hidden /></span>
        <div className="mr-auto min-w-0">
          <h2 id="h-voice" className="text-sm font-medium text-muted-foreground">Current voice</h2>
          {page.voice ? (
            <>
              <p className="font-semibold">{voiceName(page.voice)}</p>
              <p className="text-sm text-muted-foreground">
                <span className="tabular-nums">{recorded} of {lines(allTakes.length)}</span> recorded in this voice.
                Each line records at its own speed, so changing the live voice&apos;s speed keeps them.
                A new voice or pitch starts unrecorded; old recordings come back if you switch back.
              </p>
            </>
          ) : (
            <p className="text-sm text-destructive">{page.voice_problem} Calls still say every line live.</p>
          )}
        </div>
        {page.voice && todo.length > 0 && (
          <Button disabled={!canRecord} onClick={() => setAsked({
            title: "Record every line not yet recorded?",
            takes: todo.map(({ ref, take }) => ({ ref, spoken: take.spoken, again: false })),
          })}>
            <Mic /> {change.record.isPending ? "Recording…" : `Record ${lines(todo.length)}`}
            <span className="font-normal opacity-80">{estimate(page, todoChars)}</span>
          </Button>
        )}
      </section>

      {ORDER.map((kind) => {
        const shown = page.phrases.filter((p) => p.kind === kind);
        if (!shown.length) return null;
        return (
          <section key={kind} aria-labelledby={`h-${kind}`} className="rounded-xl border bg-card">
            <div className="border-b px-5 py-3.5">
              <h2 id={`h-${kind}`} className="font-semibold">{KINDS[kind].title}</h2>
              <p className="max-w-2xl text-sm text-muted-foreground">{KINDS[kind].about}</p>
            </div>
            <div className="divide-y">
              {shown.map((p, i) => {
                const label = kind === "greeting"
                  ? (p.clinic_id ? `${p.clinic_name}'s own greeting` : "Shared greeting")
                  : kind === "filler" ? `Line ${i + 1}` : KINDS[kind].title;
                return (
                  <PhraseCard key={p.id} phrase={p} label={label} canRecord={canRecord}
                    speed={{ min: page.pace_min, max: page.pace_max, busy: change.pace.isPending || change.record.isPending }}
                    onSpeed={(pace) => change.pace.mutate({ id: p.id, pace })}
                    onEdit={() => edit(p, label)}
                    onRecord={(takes) => ask(`${takes.some((t) => t.recorded_at) ? "Record again" : "Record"}: ${label}?`, p, takes)} />
                );
              })}
            </div>
          </section>
        );
      })}

      <ClinicGreetings page={page} pending={change.sharedGreeting.isPending}
        onOwn={ownGreeting} onShared={(id) => change.sharedGreeting.mutate(id)} />

      {editing && <EditDialog editing={editing} maxChars={page.max_chars} onClose={() => setEditing(null)} />}
      <RecordDialog asked={asked} page={page} onCancel={() => setAsked(null)}
        onRecord={(takes) => { setAsked(null); change.record.mutate(takes); }} />
    </>
  );
}
