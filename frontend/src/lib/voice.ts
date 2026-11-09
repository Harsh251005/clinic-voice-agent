"use client";
// Voice & phrases (admin): the receptionist's fixed lines and their
// recordings. Data hooks and the words for what the API sends.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, unwrap, type Schemas } from "@/lib/api/client";

export type VoicePage = Schemas["VoicePage"];
export type Phrase = Schemas["PhraseOut"];
export type Take = Schemas["Take"];
export type TakeRef = Schemas["TakeRef"];

export const voiceKey = ["admin", "voice"] as const;

export function useVoicePage() {
  return useQuery({ queryKey: voiceKey, queryFn: () => unwrap(api.GET("/api/admin/voice")) });
}

/** Every change answers with the whole page: shown at once, and the problems
 *  bell is asked again (a failed recording opens one). */
export function useVoiceChanges() {
  const qc = useQueryClient();
  const show = (page: VoicePage) => {
    qc.setQueryData(voiceKey, page);
    qc.invalidateQueries({ queryKey: ["problems"] });
  };
  const fail = (e: Error) => toast.error(e.message);

  const editPhrase = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Schemas["PhraseIn"] }) =>
      unwrap(api.PUT("/api/admin/voice/phrases/{phrase_id}", { params: { path: { phrase_id: id } }, body })),
    onSuccess: (page) => { show(page); toast.success("Saved. Calls say it live until you record it."); },
  });
  const ownGreeting = useMutation({
    mutationFn: ({ clinicId, body }: { clinicId: number; body: Schemas["PhraseIn"] }) =>
      unwrap(api.PUT("/api/admin/voice/clinics/{clinic_id}/greeting", { params: { path: { clinic_id: clinicId } }, body })),
    onSuccess: (page) => { show(page); toast.success("Saved. This clinic now has its own greeting."); },
  });
  const sharedGreeting = useMutation({
    mutationFn: (clinicId: number) =>
      unwrap(api.DELETE("/api/admin/voice/clinics/{clinic_id}/greeting", { params: { path: { clinic_id: clinicId } } })),
    onSuccess: (page) => { show(page); toast.success("Back to the shared greeting."); },
    onError: fail,
  });
  const record = useMutation({
    mutationFn: (takes: TakeRef[]) => unwrap(api.POST("/api/admin/voice/record", { body: { takes } })),
    onSuccess: (r) => {
      show(r.page);
      if (r.failed) toast.error(r.recorded ? `Recorded ${lines(r.recorded)}, then stopped. ${r.failed}` : r.failed);
      else toast.success(`Recorded ${lines(r.recorded)}. Calls play ${r.recorded === 1 ? "it" : "them"} from now on.`);
    },
    onError: fail,
  });
  return { editPhrase, ownGreeting, sharedGreeting, record };
}

export function suggestHindi(english: string, clinicId?: number) {
  return unwrap(api.POST("/api/admin/voice/translate", { body: { english, clinic_id: clinicId ?? null } }));
}

// ---------- words ----------

export const lines = (n: number) => `${n} line${n === 1 ? "" : "s"}`;

export const KINDS: Record<Phrase["kind"], { title: string; about: string }> = {
  greeting: {
    title: "Greeting",
    about: "The first thing every caller hears. The caller can't talk over it. {clinic} becomes each clinic's name in Hindi.",
  },
  filler: {
    title: "“One moment” lines",
    about: "Said while she looks something up, when the model said nothing first. One of the three at random, never the same twice in a row.",
  },
  goodbye_fallback: {
    title: "Goodbye",
    about: "Only when the model hangs up without writing its own goodbye. Her usual goodbye sums up the call and is always said live.",
  },
  goodbye_time_limit: {
    title: "Time-limit goodbye",
    about: "When a call reaches its time limit. The caller can't talk over it.",
  },
};

export const ORDER: Phrase["kind"][] = ["greeting", "filler", "goodbye_fallback", "goodbye_time_limit"];

export const refOf = (p: Phrase, t: Take): TakeRef => ({ phrase_id: p.id, clinic_id: t.clinic_id });

/** Every take not recorded in the current voice. */
export function missing(page: VoicePage): { ref: TakeRef; take: Take }[] {
  return page.phrases.flatMap((p) => p.takes.filter((t) => t.key && !t.recorded_at).map((t) => ({ ref: refOf(p, t), take: t })));
}

/** "≈ ₹0.42" for these words in the current voice, or "" with no price set. */
export function estimate(page: VoicePage, chars: number): string {
  const per = page.rupees_per_1000_chars;
  if (per == null) return "";
  const rupees = (chars / 1000) * per;
  return `≈ ₹${rupees < 0.01 ? "0.01" : rupees.toFixed(2)}`;
}

export function voiceName(v: NonNullable<VoicePage["voice"]>): string {
  const vendor = v.vendor === "sarvam" ? "Sarvam" : v.vendor;
  const tune = [v.pace != null && `pace ${v.pace}`, v.pitch != null && `pitch ${v.pitch}`].filter(Boolean).join(", ");
  return `${vendor} ${v.model}, ${v.voice}${tune ? ` (${tune})` : ""}`;
}

export function recordedOn(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}
