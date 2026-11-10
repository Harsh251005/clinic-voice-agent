"use client";
// The main rules every clinic's receptionist follows (Harsh, 2026-11-10:
// editable by the admin). Blank means the default rules in code; saving the
// default text unchanged keeps it blank, so later code updates still reach it.
import { RotateCcw, TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { words } from "@/lib/receptionist";

export function RulesEditor({ value, fallback, maxWords, onChange }: {
  value: string; fallback: string; maxWords: number; onChange: (rules: string) => void;
}) {
  const shown = value || fallback;
  const count = words(shown);
  const edited = value.trim() !== "" && value.trim() !== fallback.trim();
  const over = count > maxWords;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium",
          edited ? "bg-warning text-warning-foreground" : "bg-muted text-muted-foreground")}>
          {edited ? "Edited" : "Default rules"}
        </span>
        <span className={cn("text-sm tabular-nums", over ? "font-medium text-destructive" : "text-muted-foreground")}
          aria-live="polite">
          {count} of {maxWords} words
        </span>
        {edited && (
          <Button type="button" variant="ghost" size="sm" className="ml-auto" onClick={() => onChange("")}>
            <RotateCcw /> Reset to default
          </Button>
        )}
      </div>
      <Textarea id="rules" aria-label="Main rules" rows={18} className="font-mono text-[13px] leading-relaxed"
        aria-invalid={over} value={shown}
        onChange={(e) => onChange(e.target.value.trim() === fallback.trim() ? "" : e.target.value)} />
      <p className="text-xs text-muted-foreground">
        <code>{"{clinic_name}"}</code> becomes each clinic&apos;s name. Each clinic&apos;s own instructions and facts
        (doctors, hours, leave, questions) are added after these rules on every call.
      </p>
      {edited && (
        <p className="flex items-start gap-2 rounded-lg bg-warning px-3 py-2 text-sm text-warning-foreground">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
          The automated quality checks test the default rules. Edited rules are only tested by your own calls, so
          try a test call after saving.
        </p>
      )}
    </div>
  );
}
