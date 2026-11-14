"use client";
// The typed chat: the admin is the caller, the receptionist answers with her
// brain only. Each tool she uses shows between the lines as it runs, with
// what she sent and what came back, the same view as a call's transcript.
import { useEffect, useRef, useState } from "react";
import { AlertCircle, Info, MessageSquarePlus, PhoneOff } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Transcript } from "@/components/calls/transcript";
import { AfterChat } from "@/components/admin/try/after-chat";
import { Composer } from "@/components/admin/try/composer";
import { CHAT_ENDED, useTryChat } from "@/lib/try";

export function TryChat({ clinicId, clinicName, onBusy }: { clinicId: number; clinicName: string; onBusy: (busy: boolean) => void }) {
  const chat = useTryChat(clinicId);
  const [toolsOpen, setToolsOpen] = useState(true);
  const bottom = useRef<HTMLDivElement>(null);
  const on = chat.status === "replying" || chat.status === "waiting";
  const busy = on || chat.status === "starting";

  useEffect(() => { onBusy(busy); }, [busy, onBusy]);
  useEffect(() => { bottom.current?.scrollIntoView({ block: "nearest", behavior: "smooth" }); }, [chat.lines.length, chat.status]);

  if (chat.status === "idle") {
    return (
      <div className="space-y-4">
        <Alert>
          <Info />
          <AlertDescription>
            You type as the caller; she answers exactly as she would on a call: same rules, same clinic details,
            same booking steps. Bookings are real in {clinicName}&apos;s diary until you erase the chat.
            Only her brain is paid for. Hearing, voice, pace and interruptions need a voice call.
          </AlertDescription>
        </Alert>
        {chat.error && <Alert variant="destructive"><AlertCircle /><AlertDescription>{chat.error}</AlertDescription></Alert>}
        <Button size="lg" onClick={chat.start}><MessageSquarePlus /> Start chat</Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <section aria-label="Conversation" className="rounded-xl border bg-card">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
          <p className="text-sm font-medium" aria-live="polite">
            {chat.status === "starting" && "She is picking up…"}
            {chat.status === "replying" && "She is answering…"}
            {chat.status === "waiting" && "Your turn"}
            {chat.status === "ended" && "Chat ended"}
          </p>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Switch id="tools-open" checked={toolsOpen} onCheckedChange={setToolsOpen} />
              <Label htmlFor="tools-open" className="text-sm font-normal text-muted-foreground">Tool details</Label>
            </div>
            {on && <Button variant="destructive" size="sm" onClick={chat.end}><PhoneOff /> End chat</Button>}
          </div>
        </div>

        <div className="max-h-[60vh] min-h-48 overflow-y-auto p-4">
          {chat.lines.length > 0 && <Transcript items={chat.lines} toolsOpen={toolsOpen} />}
          {(chat.status === "starting" || chat.status === "replying") && <Typing />}
          {chat.status === "ended" && (
            <p className="mt-4 text-center text-sm text-muted-foreground">{CHAT_ENDED[chat.endReason] ?? "The chat ended."}</p>
          )}
          <div ref={bottom} />
        </div>

        {on && (
          <div className="border-t p-3">
            <Composer canSend={chat.status === "waiting"} onSend={chat.say} />
          </div>
        )}
      </section>

      {chat.error && <Alert variant="destructive"><AlertCircle /><AlertDescription>{chat.error}</AlertDescription></Alert>}

      {chat.status === "ended" && (
        <>
          {chat.callId !== null && <AfterChat callId={chat.callId} onErased={chat.clear} />}
          <Button onClick={chat.start}><MessageSquarePlus /> New chat</Button>
        </>
      )}
    </div>
  );
}

/** Three dots on her side while she works. */
function Typing() {
  return (
    <div className="mt-3 flex justify-end" role="status" aria-label="She is answering">
      <div className="flex gap-1 rounded-2xl rounded-br-md bg-accent px-4 py-3.5">
        {[0, 150, 300].map((delay) => (
          <span key={delay} className="size-1.5 animate-bounce rounded-full bg-accent-foreground/60" style={{ animationDelay: `${delay}ms` }} />
        ))}
      </div>
    </div>
  );
}
