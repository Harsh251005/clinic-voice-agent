"use client";
// The greeting this clinic's callers hear, on the admin's page for the clinic
// (Harsh, 2026-11-12): the shared one with its name, or its own words.
import { useState } from "react";
import { Pencil, Undo2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EditDialog } from "@/components/admin/voice/edit-dialog";
import { Section } from "@/components/setup/section";
import { useVoiceChanges, useVoicePage } from "@/lib/voice";

export function Greeting({ clinicId }: { clinicId: number }) {
  const page = useVoicePage();
  const change = useVoiceChanges();
  const [editing, setEditing] = useState(false);
  if (page.isError) return <Section title="Greeting"><p className="text-sm text-destructive">{page.error.message}</p></Section>;
  if (!page.data) return <Skeleton className="h-40" />;

  const greetings = page.data.phrases.filter((p) => p.kind === "greeting");
  const own = greetings.find((p) => p.clinic_id === clinicId);
  const shared = greetings.find((p) => p.clinic_id == null);
  const clinic = page.data.clinics.find((c) => c.id === clinicId);
  // Exactly what is said: the shared greeting with this clinic's name in it, or its own words.
  const spoken = own?.text
    ?? shared?.takes.find((t) => t.clinic_id === clinicId)?.spoken
    ?? (shared?.text ?? "").replaceAll("{clinic}", clinic?.spoken_name ?? "");
  const english = own?.source ?? (shared?.source ?? "").replaceAll("{clinic}", clinic?.name ?? "the clinic");

  return (
    <Section title="Greeting"
      description={own ? "The first thing callers hear. This clinic has its own words." : "The first thing callers hear. This clinic uses the shared greeting, with its own name."}
      action={
        <div className="flex shrink-0 flex-wrap justify-end gap-2">
          {own && (
            <Button variant="ghost" size="sm" disabled={change.sharedGreeting.isPending} onClick={() => change.sharedGreeting.mutate(clinicId)}>
              <Undo2 /> Use the shared one
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
            <Pencil /> {own ? "Change the words" : "Give it its own words"}
          </Button>
        </div>
      }>
      <blockquote className="rounded-lg bg-muted/60 px-4 py-3">
        <p lang="hi" className="text-base leading-relaxed">{spoken}</p>
        {english && <p className="mt-2 text-sm text-muted-foreground">{english}</p>}
      </blockquote>
      {editing && (
        <EditDialog maxChars={page.data.max_chars} onClose={() => setEditing(false)} editing={{
          title: `${clinic?.name ?? "This clinic"}: its own greeting`, source: english, text: spoken, greeting: "own", clinicId,
          save: (body, done, failed) => change.ownGreeting.mutate({ clinicId, body }, { onSuccess: done, onError: (e) => failed(e.message) }),
        }} />
      )}
    </Section>
  );
}
