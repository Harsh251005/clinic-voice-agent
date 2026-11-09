"use client";
// One phrase: its English, the Hindi she says, and each way calls say it
// (the shared greeting once per clinic) with its recording status.
import { CircleCheck, CircleDashed, Mic, Pencil } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { recordedOn, type Phrase, type Take } from "@/lib/voice";
import { PlayButton } from "./play-button";

export function Status({ take }: { take: Take }) {
  return take.recorded_at ? (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-success px-2.5 py-0.5 text-xs font-medium whitespace-nowrap text-success-foreground">
      <CircleCheck className="size-3.5" aria-hidden /> Recorded {recordedOn(take.recorded_at)}
      {take.duration_s != null && <span className="tabular-nums">· {take.duration_s.toFixed(1)} s</span>}
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium whitespace-nowrap text-muted-foreground">
      <CircleDashed className="size-3.5" aria-hidden /> Said live
    </span>
  );
}

export function PhraseCard({ phrase, label, canRecord, onEdit, onRecord }: {
  phrase: Phrase; label: string; canRecord: boolean; onEdit: () => void; onRecord: (takes: Take[]) => void;
}) {
  const perClinic = phrase.kind === "greeting";
  return (
    <article className="px-5 py-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <p className="text-xs font-medium text-muted-foreground">{label}</p>
          <p lang="hi" className="text-[17px] leading-relaxed">{phrase.text}</p>
          <p className="text-sm text-muted-foreground">{phrase.source}</p>
        </div>
        <Button variant="ghost" size="sm" onClick={onEdit} aria-label={`Change ${label}`}><Pencil /> Change</Button>
      </div>

      {phrase.takes.length === 0 ? (
        <p className="mt-3 text-sm text-muted-foreground">Every clinic has its own greeting, so this one is not said.</p>
      ) : (
        <ul className={cn("mt-3 divide-y rounded-lg border", !perClinic && "border-dashed")}>
          {phrase.takes.map((t) => (
            <li key={t.clinic_id ?? "all"} className="flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2">
              <div className="mr-auto min-w-0">
                {perClinic && <p className="truncate text-sm font-medium">{t.clinic_name}</p>}
                <Status take={t} />
              </div>
              {t.key && t.recorded_at && <PlayButton clipKey={t.key} version={t.recorded_at} label={perClinic ? `${label} for ${t.clinic_name}` : label} />}
              {canRecord && (
                <Button variant={t.recorded_at ? "ghost" : "outline"} size="sm" onClick={() => onRecord([t])}
                  aria-label={`${t.recorded_at ? "Re-record" : "Record"} ${perClinic ? `${label} for ${t.clinic_name}` : label}`}>
                  <Mic /> {t.recorded_at ? "Re-record" : "Record"}
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}
