"use client";
// Admin > Try: a typed chat with a clinic's receptionist (her brain only).
// The API holds the chat; this keeps the page in step with it by asking
// again while she answers, so each tool shows as it runs.
import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { adminKeys } from "@/lib/admin";
import { api, ApiError, unwrap, type Schemas } from "@/lib/api/client";

export type ChatLine = Schemas["TranscriptItem"];
type Chat = Schemas["TryChat"];
export type ChatStatus = "idle" | "starting" | Chat["status"];

const WHILE_REPLYING_MS = 400; // tools and her reply appear as they happen
const WHILE_WAITING_MS = 5000; // only to notice a chat that ended itself (time limit, quiet spell)

/** How a chat ended, in the admin's words. */
export const CHAT_ENDED: Record<string, string> = {
  agent_ended: "She said goodbye and hung up.",
  caller_left: "You ended the chat.",
  time_limit: "It reached this clinic's longest call, so she said goodbye and hung up.",
  shutdown: "The server stopped, which ended the chat.",
  error: "It ended on an error. The trace has the details.",
};

export function useTryChat(clinicId: number | null) {
  const [status, setStatus] = useState<ChatStatus>("idle");
  const [lines, setLines] = useState<ChatLine[]>([]);
  const [callId, setCallId] = useState<number | null>(null);
  const [endReason, setEndReason] = useState("");
  const [error, setError] = useState("");
  const chatId = useRef<string | null>(null);
  const next = useRef(0); // how many lines the page already has

  /** Take in an answer asked with `after`: only lines the page lacks. */
  const take = useCallback((chat: Chat, after: number) => {
    if (chat.id !== chatId.current) return; // an answer for a chat since replaced
    const fresh = chat.lines.slice(Math.max(0, next.current - after));
    next.current = Math.max(next.current, chat.next);
    if (fresh.length) setLines((old) => [...old, ...fresh]);
    setCallId(chat.call_id);
    setEndReason(chat.end_reason);
    setStatus(chat.status);
  }, []);

  const lost = useCallback((err: unknown) => {
    if (err instanceof ApiError && err.status === 404) { // forgotten, or the server restarted
      chatId.current = null;
      setEndReason("shutdown");
      setStatus("ended");
    }
    setError(err instanceof Error ? err.message : "Something went wrong.");
  }, []);

  // Keep asking while a chat is on.
  useEffect(() => {
    if (status !== "replying" && status !== "waiting") return;
    const id = chatId.current;
    if (!id) return;
    const timer = setTimeout(async () => {
      const after = next.current;
      try {
        take(await unwrap(api.GET("/api/admin/try/chats/{chat_id}", { params: { path: { chat_id: id }, query: { after } } })), after);
      } catch (err) {
        if (chatId.current === id) lost(err);
      }
    }, status === "replying" ? WHILE_REPLYING_MS : WHILE_WAITING_MS);
    return () => clearTimeout(timer);
  }, [status, lines, take, lost]);

  const hangUp = useCallback((id: string) =>
    unwrap(api.DELETE("/api/admin/try/chats/{chat_id}", { params: { path: { chat_id: id }, query: { after: next.current } } })), []);

  // Leaving the page hangs up, as leaving a call does.
  useEffect(() => () => { if (chatId.current) void hangUp(chatId.current).catch(() => {}); }, [hangUp]);

  async function start() {
    if (clinicId === null) return;
    chatId.current = null;
    next.current = 0;
    setLines([]); setCallId(null); setEndReason(""); setError("");
    setStatus("starting");
    try {
      const chat = await unwrap(api.POST("/api/admin/clinics/{clinic_id}/try/chat", { params: { path: { clinic_id: clinicId } } }));
      chatId.current = chat.id;
      take(chat, 0);
    } catch (err) {
      setStatus("idle");
      setError(err instanceof Error ? err.message : "The chat could not start.");
    }
  }

  async function say(text: string) {
    const id = chatId.current;
    if (!id || status !== "waiting") return;
    setError("");
    setStatus("replying");
    const after = next.current;
    try {
      take(await unwrap(api.POST("/api/admin/try/chats/{chat_id}/messages", {
        params: { path: { chat_id: id }, query: { after } }, body: { text },
      })), after);
    } catch (err) {
      setStatus("waiting");
      lost(err);
    }
  }

  async function end() {
    const id = chatId.current;
    if (!id) return;
    const after = next.current;
    try {
      take(await hangUp(id), after);
    } catch (err) {
      lost(err);
    }
  }

  /** Back to the start: after erasing, or to pick another clinic. */
  function clear() {
    chatId.current = null;
    next.current = 0;
    setLines([]); setCallId(null); setEndReason(""); setError("");
    setStatus("idle");
  }

  return { status, lines, callId, endReason, error, start, say, end, clear };
}

/** Erase a finished test call (a chat's record) with everything it changed. */
export function useEraseTry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (callId: number) => unwrap(api.DELETE("/api/admin/calls/{call_id}", { params: { path: { call_id: callId } } })),
    onSuccess: () => {
      toast.success("Erased. Everything it booked, moved or cancelled is undone.");
      return queryClient.invalidateQueries({ queryKey: adminKeys.all });
    },
    onError: (err) => toast.error(err.message),
  });
}
