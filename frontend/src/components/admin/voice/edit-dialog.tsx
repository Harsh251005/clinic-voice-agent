"use client";
// Change a phrase: write the English, get the Hindi she will say (suggested,
// then yours to edit), save. A greeting must keep what every caller is told.
import { useState } from "react";
import { Languages, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { suggestHindi } from "@/lib/voice";

export type Editing = {
  title: string;
  source: string;
  text: string;
  greeting: "shared" | "own" | null;
  clinicId?: number; // whose names to spell the same way
  save: (body: { source: string; text: string }, done: () => void, failed: (message: string) => void) => void;
};

export function EditDialog({ editing, maxChars, onClose }: { editing: Editing; maxChars: number; onClose: () => void }) {
  const [source, setSource] = useState(editing.source);
  const [text, setText] = useState(editing.text);
  const [suggestedFor, setSuggestedFor] = useState(editing.source);
  const [busy, setBusy] = useState<"suggest" | "save" | null>(null);
  const [error, setError] = useState("");

  const suggest = async () => {
    setBusy("suggest");
    setError("");
    try {
      setText((await suggestHindi(source, editing.clinicId)).text);
      setSuggestedFor(source);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const save = () => {
    setBusy("save");
    setError("");
    editing.save({ source, text }, onClose, (message) => { setError(message); setBusy(null); });
  };

  const stale = source.trim() !== suggestedFor.trim();
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
        <form onSubmit={(e) => { e.preventDefault(); save(); }} className="space-y-4">
          <DialogHeader>
            <DialogTitle>{editing.title}</DialogTitle>
            <DialogDescription>
              Write it in English and get the Hindi she says. Read the Hindi before saving: it is exactly what callers hear.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-1.5">
            <Label htmlFor="phrase-source">In English</Label>
            <Textarea id="phrase-source" value={source} maxLength={maxChars} rows={3} onChange={(e) => setSource(e.target.value)} />
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button type="button" variant="outline" onClick={suggest} disabled={!source.trim() || busy !== null}>
              {busy === "suggest" ? <Loader2 className="animate-spin" /> : <Languages />} Suggest Hindi
            </Button>
            {stale && text && <p className="text-xs text-warning-foreground">The English changed since this Hindi. Suggest again, or edit the Hindi.</p>}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="phrase-text">What she says (Hindi)</Label>
            <Textarea id="phrase-text" lang="hi" value={text} maxLength={maxChars} rows={4} className="text-base leading-relaxed"
              onChange={(e) => setText(e.target.value)} />
            <p className="flex justify-between gap-3 text-xs text-muted-foreground">
              <span>
                {editing.greeting
                  ? `Must still say ऑटोमेटेड असिस्टेंट and that the call is saved as text (टेक्स्ट)${editing.greeting === "shared" ? ", and keep {clinic}" : ""}.`
                  : "Devanagari only, with । ? and , for punctuation."}
              </span>
              <span className="shrink-0 tabular-nums">{text.length}/{maxChars}</span>
            </p>
          </div>

          {error && <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={!source.trim() || !text.trim() || busy !== null}>
              {busy === "save" ? "Saving…" : "Save"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
