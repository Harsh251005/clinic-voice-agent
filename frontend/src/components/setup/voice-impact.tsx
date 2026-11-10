"use client";
// Before a clinic's voice changes (Harsh, 2026-11-10): how many of its
// recorded lines the new voice leaves said live until they are recorded again.
import { useQuery } from "@tanstack/react-query";
import { TriangleAlert } from "lucide-react";
import { api, unwrap } from "@/lib/api/client";

export function VoiceImpact({ clinicId, model, speaker, pitch }: { clinicId: number; model: string; speaker: string; pitch: number | null }) {
  const impact = useQuery({
    queryKey: ["admin", "voice-impact", clinicId, model, speaker, pitch],
    queryFn: () => unwrap(api.GET("/api/admin/voice/impact", {
      params: { query: { clinic_id: clinicId, model, speaker, ...(pitch == null ? {} : { pitch }) } },
    })),
  });
  if (!impact.data) return null;
  const lost = impact.data.recorded_now - impact.data.recorded_after;
  if (lost <= 0) return null;
  return (
    <p role="status" className="mt-4 flex items-start gap-2 rounded-lg bg-warning px-3 py-2 text-sm text-warning-foreground">
      <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
      <span>
        This voice leaves {lost} of this clinic&apos;s {impact.data.recorded_now} recorded line{impact.data.recorded_now === 1 ? "" : "s"} said
        live until you record {lost === 1 ? "it" : "them"} again on Voice &amp; phrases. Recorded lines in the old voice
        come back if you switch back.
      </span>
    </p>
  );
}
