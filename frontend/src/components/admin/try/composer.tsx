"use client";
// Where the admin types the caller's turn. Enter sends; Shift+Enter is a new line.
import { useEffect, useRef, useState } from "react";
import { SendHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

export function Composer({ canSend, onSend }: { canSend: boolean; onSend: (text: string) => void }) {
  const [text, setText] = useState("");
  const box = useRef<HTMLTextAreaElement>(null);
  useEffect(() => { if (canSend) box.current?.focus(); }, [canSend]); // straight back to typing after her reply

  function send() {
    const said = text.trim();
    if (!said || !canSend) return;
    onSend(said);
    setText("");
  }

  return (
    <form className="flex items-end gap-2" onSubmit={(e) => { e.preventDefault(); send(); }}>
      <Textarea ref={box} rows={1} maxLength={1000} value={text} aria-label="What the caller says"
        placeholder="Type what a caller would say, in Hindi, Hinglish or English"
        className="max-h-40 min-h-11 resize-none"
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(); } }} />
      <Button type="submit" size="icon" className="size-11 shrink-0" disabled={!canSend || !text.trim()} aria-label="Send">
        <SendHorizontal />
      </Button>
    </form>
  );
}
