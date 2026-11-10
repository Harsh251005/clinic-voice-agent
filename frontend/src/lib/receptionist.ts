"use client";
// Admin > Receptionist: what every clinic's receptionist shares (rules,
// brain, hearing, voice model, turn-taking, greeting). Data hooks and words.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, unwrap, type Schemas } from "@/lib/api/client";

export type SystemSettings = Schemas["SystemSettingsOut"];
export type SystemSettingsIn = Schemas["SystemSettingsIn"];

export const receptionistKey = ["admin", "receptionist"] as const;

export function useReceptionist() {
  return useQuery({ queryKey: receptionistKey, queryFn: () => unwrap(api.GET("/api/admin/receptionist")) });
}

export function useSaveReceptionist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: SystemSettingsIn) => unwrap(api.PUT("/api/admin/receptionist", { body })),
    onSuccess: (page) => {
      qc.setQueryData(receptionistKey, page);
      toast.success("Saved. Every clinic's calls use it from the next call.");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}

export const words = (text: string) => text.trim().split(/\s+/).filter(Boolean).length;

/** The fields the form edits: everything but what the server only reports. */
export type Editable = Omit<SystemSettings, "default_rules" | "rules_max_words" | "blank_means" | "limits" | "llm_vendors">;

export function editable(s: SystemSettings): Editable {
  return {
    rules: s.rules, hindi_llm: s.hindi_llm, sarvam_llm_model: s.sarvam_llm_model, openai_llm_model: s.openai_llm_model,
    sarvam_stt_model: s.sarvam_stt_model, sarvam_stt_language: s.sarvam_stt_language, sarvam_stt_mode: s.sarvam_stt_mode,
    min_endpointing_delay: s.min_endpointing_delay,
    number_endpointing_delay: s.number_endpointing_delay, interrupt_min_speech: s.interrupt_min_speech,
    vad_min_silence: s.vad_min_silence, greeting_interruptible: s.greeting_interruptible,
  };
}

export const TIMINGS: { key: "min_endpointing_delay" | "number_endpointing_delay" | "interrupt_min_speech" | "vad_min_silence"; label: string; hint: string }[] = [
  { key: "min_endpointing_delay", label: "End-of-turn wait (seconds)", hint: "Silence after the caller stops before she answers. Longer = fewer interruptions, slower replies." },
  { key: "number_endpointing_delay", label: "Wait while reading a number (seconds)", hint: "Used instead while the caller reads out a mobile number, so a pause between digits doesn't end the turn." },
  { key: "interrupt_min_speech", label: "Talk-over sensitivity (seconds)", hint: "How long the caller must speak before she stops talking. Shorter = she stops sooner, but coughs may stop her too." },
  { key: "vad_min_silence", label: "Pause that ends a phrase (seconds)", hint: "How long a pause splits the caller's speech into separate phrases." },
];
