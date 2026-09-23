"use client";
import { useState } from "react";
import Link from "next/link";
import { Check, CircleCheck, Circle, Copy, Headset } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import type { Schemas } from "@/lib/api/client";
import { setupSteps } from "@/lib/clinic-day";
import { cn } from "@/lib/utils";

/** The receptionist as something the clinic owns: ready or not, what's left
 *  to set up, and a way to try it and share it. */
export function Receptionist({ clinic }: { clinic: Schemas["Clinic"] }) {
  const steps = setupSteps(clinic);
  const done = steps.filter((s) => s.done).length;
  const ready = done === steps.length;
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(clinic.call_link);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("Couldn't copy. Open Clinic settings to copy the link by hand.");
    }
  };

  return (
    <section aria-labelledby="receptionist" className="rounded-xl border bg-card">
      <div className="flex items-start gap-3 border-b px-5 py-4">
        <span className={cn("grid size-9 shrink-0 place-items-center rounded-lg", ready ? "bg-success text-success-foreground" : "bg-warning text-warning-foreground")}>
          <Headset className="size-5" aria-hidden />
        </span>
        <div>
          <h2 id="receptionist" className="font-semibold">Your receptionist</h2>
          <p className="text-sm text-muted-foreground">
            {ready ? "Ready. It answers from your clinic's details." : `Setup ${done} of ${steps.length} done`}
          </p>
        </div>
      </div>

      {!ready && (
        <>
          <div className="px-5 pt-4" aria-hidden>
            <div className="h-1.5 overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${(done / steps.length) * 100}%` }} />
            </div>
          </div>
          <ol className="space-y-1 p-3">
            {steps.map((s) => (
              <li key={s.id}>
                <Link href={`/clinics/${clinic.id}/setup?tab=${s.tab}`}
                  className={cn("flex gap-3 rounded-lg px-2 py-2 hover:bg-muted", s.done && "pointer-events-none")}>
                  {s.done
                    ? <CircleCheck className="mt-0.5 size-5 shrink-0 text-success-foreground" aria-label="Done" />
                    : <Circle className="mt-0.5 size-5 shrink-0 text-muted-foreground/50" aria-label="To do" />}
                  <span>
                    <span className={cn("block text-sm font-medium", s.done && "text-muted-foreground line-through")}>{s.label}</span>
                    {!s.done && <span className="block text-xs text-muted-foreground">{s.hint}</span>}
                  </span>
                </Link>
              </li>
            ))}
          </ol>
        </>
      )}

      <div className="flex gap-2 border-t p-4">
        <Button variant={ready ? "default" : "outline"} className="flex-1" asChild>
          <a href={clinic.call_link} target="_blank" rel="noreferrer"><Headset /> Try a call</a>
        </Button>
        <Button variant="outline" className="flex-1" onClick={copy}>
          {copied ? <Check /> : <Copy />} {copied ? "Copied" : "Copy link"}
        </Button>
      </div>
    </section>
  );
}
