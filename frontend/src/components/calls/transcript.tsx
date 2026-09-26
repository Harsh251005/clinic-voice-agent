"use client";
// A call's transcript as a conversation: the caller on the left, the
// receptionist on the right, each tool it used as a line between. Used by
// the clinic's Calls page and by the operator after a logged opening.
import { CircleCheck, CircleX, TriangleAlert, Wrench } from "lucide-react";
import type { Schemas } from "@/lib/api/client";
import { cn } from "@/lib/utils";

export function offset(tMs: number): string {
  const s = Math.floor(tMs / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function Transcript({ items, showTools = true }: { items: Schemas["TranscriptItem"][]; showTools?: boolean }) {
  if (!items.length) return <p className="text-sm text-muted-foreground">Nothing was said on this call.</p>;
  return (
    <ol className="space-y-3">
      {items.map((item, i) => {
        if (item.role === "tool") {
          if (!showTools) return null;
          return (
            <li key={i} className="flex justify-center">
              <details className="group w-full max-w-xl rounded-lg border border-dashed px-3 py-2 text-xs">
                <summary className="flex cursor-pointer list-none items-center gap-2 text-muted-foreground">
                  <Wrench className="size-3.5" aria-hidden />
                  <span className="font-mono text-foreground">{item.tool}</span>
                  {item.ok
                    ? <span className="inline-flex items-center gap-1 text-success-foreground"><CircleCheck className="size-3.5" aria-hidden /> worked</span>
                    : <span className="inline-flex items-center gap-1 text-destructive"><CircleX className="size-3.5" aria-hidden /> refused</span>}
                  <span className="ml-auto tabular-nums">{offset(item.t_ms)}</span>
                </summary>
                {item.args && item.args !== "{}" && <pre className="mt-2 overflow-x-auto rounded bg-muted p-2 whitespace-pre-wrap">{item.args}</pre>}
                <p className="mt-2 whitespace-pre-wrap text-muted-foreground">{item.text}</p>
              </details>
            </li>
          );
        }
        if (item.role === "error") {
          return (
            <li key={i} className="flex items-start justify-center gap-2 text-xs text-destructive">
              <TriangleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden /> <span className="break-all">{item.text}</span>
            </li>
          );
        }
        const caller = item.role === "caller";
        return (
          <li key={i} className={cn("flex", caller ? "justify-start" : "justify-end")}>
            <div className={cn("max-w-[85%] rounded-2xl px-4 py-2.5", caller ? "rounded-bl-md bg-muted" : "rounded-br-md bg-accent text-accent-foreground")}>
              <p className="mb-0.5 text-[11px] font-medium opacity-70">
                {caller ? "Caller" : "Receptionist"} · <span className="tabular-nums">{offset(item.t_ms)}</span>
                {item.interrupted && " · cut off by the caller"}
              </p>
              <p className="whitespace-pre-wrap">{item.text}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
