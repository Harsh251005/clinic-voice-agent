"use client";
// The operator's admin panel: data hooks and the words for what the API sends.
import { useQuery } from "@tanstack/react-query";
import { api, unwrap, type Schemas } from "@/lib/api/client";

export type CallFilters = {
  clinic_id?: number;
  outcome?: string;
  status?: "dropped";
  with_errors?: boolean;
};

export const adminKeys = {
  all: ["admin"] as const,
  health: (days: number) => ["admin", "health", days] as const,
  calls: (f: CallFilters) => ["admin", "calls", f] as const,
  call: (id: number) => ["admin", "call", id] as const,
  errors: (days: number) => ["admin", "errors", days] as const,
  clinics: ["admin", "clinics"] as const,
};

export function useHealth(days: number) {
  return useQuery({
    queryKey: adminKeys.health(days),
    queryFn: () => unwrap(api.GET("/api/admin/health", { params: { query: { days } } })),
    refetchInterval: 60_000,
  });
}

export function useCalls(filters: CallFilters, beforeId?: number) {
  return useQuery({
    queryKey: [...adminKeys.calls(filters), beforeId ?? null],
    queryFn: () => unwrap(api.GET("/api/admin/calls", { params: { query: { ...filters, before_id: beforeId } } })),
    refetchInterval: beforeId ? false : 30_000,
  });
}

export function useCallTrace(callId: number) {
  return useQuery({
    queryKey: adminKeys.call(callId),
    queryFn: () => unwrap(api.GET("/api/admin/calls/{call_id}", { params: { path: { call_id: callId } } })),
  });
}

export function useErrorGroups(days: number) {
  return useQuery({
    queryKey: adminKeys.errors(days),
    queryFn: () => unwrap(api.GET("/api/admin/errors", { params: { query: { days } } })),
  });
}

export function useAdminClinics() {
  return useQuery({
    queryKey: adminKeys.clinics,
    queryFn: () => unwrap(api.GET("/api/admin/clinics")),
  });
}

// ---------- words ----------

export const OUTCOMES: Record<string, string> = {
  booked: "Booked",
  moved: "Moved",
  cancelled: "Cancelled",
  info_only: "Question only",
  no_action: "Said nothing",
  failed: "Failed",
};

export const END_REASONS: Record<string, string> = {
  caller_left: "Caller hung up",
  agent_ended: "Receptionist ended it",
  time_limit: "Hit the time limit",
  shutdown: "Worker stopped",
  error: "Ended on an error",
};

/** Each timing, as what the caller experiences. */
export const STAGES: Record<string, { label: string; hint: string }> = {
  stt: { label: "Hearing", hint: "STT: speech to words" },
  eou: { label: "End of turn", hint: "deciding the caller finished" },
  llm: { label: "Thinking", hint: "LLM: first word of the reply" },
  tts: { label: "Voice", hint: "TTS: first sound of the reply" },
  reply: { label: "Caller's wait", hint: "end of their speech to our voice" },
};

export function ms(value: number | null | undefined): string {
  if (value == null) return "–";
  return value >= 1000 ? `${(value / 1000).toFixed(value >= 10_000 ? 0 : 1)} s` : `${value} ms`;
}

export function duration(seconds: number | null): string {
  if (seconds == null) return "–";
  const m = Math.floor(seconds / 60);
  return m ? `${m}m ${String(seconds % 60).padStart(2, "0")}s` : `${seconds}s`;
}

/** An instant from the API (UTC) in the viewer's own time. */
export function when(iso: string): string {
  const d = new Date(iso);
  const today = new Date();
  const sameDay = d.toDateString() === today.toDateString();
  const time = d.toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" });
  return sameDay ? `Today, ${time}` : `${d.toLocaleDateString("en-IN", { day: "numeric", month: "short" })}, ${time}`;
}

/** "sarvam/saaras:v3 · openai/gpt-6-luna · …" → the vendors only, for tight spaces. */
export function vendorsOf(stack: string): string {
  return stack.split(" · ").map((part) => part.split("/")[0]).join(" · ");
}

export type CallSummary = Schemas["CallSummary"];
