"use client";
// Which greeting each clinic's callers hear: the shared one, or its own.
import { Building2, Undo2, Pencil } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { VoicePage } from "@/lib/voice";

export function ClinicGreetings({ page, onOwn, onShared, pending }: {
  page: VoicePage; onOwn: (clinicId: number) => void; onShared: (clinicId: number) => void; pending: boolean;
}) {
  return (
    <section aria-labelledby="h-clinic-greetings" className="rounded-xl border bg-card">
      <div className="border-b px-5 py-3.5">
        <h2 id="h-clinic-greetings" className="font-semibold">Greeting by clinic</h2>
        <p className="text-sm text-muted-foreground">
          Every clinic uses the shared greeting with its own name, unless you give it its own words.
        </p>
      </div>
      {page.clinics.length === 0 ? (
        <p className="px-5 py-4 text-sm text-muted-foreground">No clinics yet.</p>
      ) : (
        <ul className="divide-y">
          {page.clinics.map((c) => (
            <li key={c.id} className="flex flex-wrap items-center gap-x-3 gap-y-2 px-5 py-3">
              <Building2 className="size-4 text-muted-foreground" aria-hidden />
              <div className="mr-auto min-w-0">
                <p className="font-medium">{c.name}</p>
                <p className="text-sm text-muted-foreground">
                  {c.own_greeting ? "Its own greeting (under Greeting, above)" : <>Shared greeting, saying <span lang="hi">{c.spoken_name}</span></>}
                </p>
              </div>
              {c.own_greeting ? (
                <Button variant="ghost" size="sm" disabled={pending} onClick={() => onShared(c.id)} aria-label={`${c.name}: use the shared greeting`}><Undo2 /> Use the shared one</Button>
              ) : (
                <Button variant="outline" size="sm" onClick={() => onOwn(c.id)} aria-label={`Give ${c.name} its own greeting`}><Pencil /> Give it its own</Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
