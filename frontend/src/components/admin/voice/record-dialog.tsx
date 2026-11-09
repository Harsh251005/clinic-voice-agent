"use client";
// Asks before any recording: it spends the voice vendor's credits. Shows
// what will be recorded, its characters and the estimated price.
import { Mic } from "lucide-react";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { estimate, lines, type TakeRef, type VoicePage } from "@/lib/voice";

export type Asked = { title: string; takes: { ref: TakeRef; spoken: string; again: boolean }[] };

export function RecordDialog({ asked, page, onCancel, onRecord }: {
  asked: Asked | null; page: VoicePage; onCancel: () => void; onRecord: (takes: TakeRef[]) => void;
}) {
  const chars = asked?.takes.reduce((n, t) => n + t.spoken.length, 0) ?? 0;
  const price = estimate(page, chars);
  const again = asked?.takes.filter((t) => t.again).length ?? 0;
  return (
    <AlertDialog open={!!asked} onOpenChange={(o) => !o && onCancel()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{asked?.title}</AlertDialogTitle>
          <AlertDialogDescription>
            {lines(asked?.takes.length ?? 0)}, {chars.toLocaleString("en-IN")} characters
            {price ? `, ${price}` : " (no price set for this voice on the Prices page)"}, charged by the voice vendor.
            {again > 0 && ` ${again === asked?.takes.length ? "Each replaces" : `${lines(again)} replace`} the current recording.`}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <ul className="max-h-48 space-y-1.5 overflow-y-auto rounded-lg bg-muted/60 p-3 text-sm" lang="hi">
          {asked?.takes.map((t) => <li key={`${t.ref.phrase_id}-${t.ref.clinic_id}`}>{t.spoken}</li>)}
        </ul>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={() => asked && onRecord(asked.takes.map((t) => t.ref))}>
            <Mic /> Record
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
