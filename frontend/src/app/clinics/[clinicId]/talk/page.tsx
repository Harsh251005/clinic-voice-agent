"use client";
// Staff call their own receptionist, exactly as a patient would: same
// languages, same voices, same tools. It is a real call (it books for real),
// so when it ends the page shows what it did, and while any test call is on
// record the page offers to erase them all, with everything they did.
import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import type { Room } from "livekit-client";
import { Eraser, Info, Mic, PhoneOff } from "lucide-react";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/app/page-header";
import { CallResult } from "@/components/admin/bits";
import { api, ApiError, unwrap, type Schemas } from "@/lib/api/client";
import { changeText, visitTime, type ClinicCall } from "@/lib/calls";
import { keys, testCallInRoom, useEraseAllTestCalls, useTestCalls } from "@/lib/queries";
import { cn } from "@/lib/utils";

type Language = Schemas["TestCallRequest"]["language"];
type State = "idle" | "connecting" | "waiting" | "live" | "ended" | "error";

const LANGUAGES: { value: Language; label: string; lang: string }[] = [
  { value: "en", label: "English", lang: "en" },
  { value: "hi", label: "हिन्दी", lang: "hi" },
];
const NO_ANSWER_MS = 20_000; // the receptionist normally joins within a few seconds
const FIND_TRIES = 15; // the record is written as the call closes: look for it for a few seconds

export default function TalkPage() {
  const clinicId = Number(useParams<{ clinicId: string }>().clinicId);
  const [language, setLanguage] = useState<Language>("hi");
  const [state, setState] = useState<State>("idle");
  const [message, setMessage] = useState("");
  const [seconds, setSeconds] = useState(0);
  const [call, setCall] = useState<ClinicCall | null>(null);
  const room = useRef<Room | null>(null);
  const roomName = useRef<string | null>(null);
  const noAnswer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const gaveUp = useRef(false); // the call never got going: there's no record to look for
  const audio = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();

  const inCall = state === "connecting" || state === "waiting" || state === "live";

  useEffect(() => () => { room.current?.disconnect(); }, []); // leaving the page hangs up

  useEffect(() => {
    if (state !== "live") return;
    const started = Date.now();
    const tick = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 500);
    return () => clearInterval(tick);
  }, [state]);

  async function findCall(name: string) {
    for (let i = 0; i < FIND_TRIES; i++) {
      try {
        const found = await testCallInRoom(clinicId, name);
        if (found.status !== "live") {
          setCall(found);
          return queryClient.invalidateQueries({ queryKey: keys.calls(clinicId) }); // the test-call count
        }
      } catch (err) {
        if (!(err instanceof ApiError && err.status === 404)) break;
      }
      await new Promise((r) => setTimeout(r, 1000));
    }
    setMessage("The call ended, but its record isn't ready yet. Find it on the Calls page to read or erase it.");
  }

  async function start() {
    setState("connecting");
    setMessage("");
    setCall(null);
    setSeconds(0);
    gaveUp.current = false;
    let pass: Schemas["TestCallPass"];
    try {
      pass = await unwrap(api.POST("/api/clinics/{clinic_id}/calls/test", {
        params: { path: { clinic_id: clinicId } }, body: { language },
      }));
    } catch (err) {
      setState("error");
      return setMessage(err instanceof Error ? err.message : "The call could not start.");
    }
    roomName.current = pass.room;

    const LK = await import("livekit-client"); // browser only
    const r = new LK.Room();
    room.current = r;
    const joined = () => { clearTimeout(noAnswer.current); setState("live"); };
    r.on(LK.RoomEvent.TrackSubscribed, (track) => {
      if (track.kind === "audio") audio.current?.appendChild(track.attach());
    })
      .on(LK.RoomEvent.ParticipantConnected, (p) => { if (p.isAgent) joined(); })
      .on(LK.RoomEvent.Disconnected, () => {
        clearTimeout(noAnswer.current);
        if (audio.current) audio.current.innerHTML = "";
        room.current = null;
        if (gaveUp.current) return;
        setState("ended");
        if (roomName.current) void findCall(roomName.current);
      });

    try {
      await r.connect(pass.url, pass.token);
      await r.localParticipant.setMicrophoneEnabled(true);
    } catch (err) {
      gaveUp.current = true;
      await r.disconnect();
      const denied = err instanceof Error && (err.name === "NotAllowedError" || /permission/i.test(err.message));
      setState("error");
      return setMessage(denied ? "Allow microphone access in your browser, then try again."
        : "The call could not connect. Check your internet and try again.");
    }
    if ([...r.remoteParticipants.values()].some((p) => p.isAgent)) return joined();
    setState("waiting");
    noAnswer.current = setTimeout(() => {
      gaveUp.current = true;
      setState("error");
      setMessage("The receptionist didn't answer. If the problem banner says it's offline, that's why.");
      void r.disconnect();
    }, NO_ANSWER_MS);
  }

  async function hangUp() {
    await room.current?.disconnect();
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Talk to your receptionist"
        description="Call it yourself, exactly as a patient would: same voice, same answers, same bookings." />

      <Alert>
        <Info />
        <AlertDescription>
          This is a real call. Anything the receptionist books, moves or cancels really happens in your diary.
          When the call ends you can erase it, which undoes all of that.
        </AlertDescription>
      </Alert>

      <section className="mx-auto max-w-md rounded-2xl border bg-card p-6 text-center shadow-sm">
        <fieldset disabled={inCall} className="mb-6">
          <legend className="mb-2 w-full text-sm text-muted-foreground">Language of the call</legend>
          <div className="grid grid-cols-2 gap-2" role="radiogroup">
            {LANGUAGES.map((l) => (
              <button key={l.value} type="button" role="radio" aria-checked={language === l.value} lang={l.lang}
                onClick={() => setLanguage(l.value)}
                className={cn("rounded-xl border px-3 py-2.5 font-semibold transition-colors disabled:opacity-50",
                  language === l.value ? "border-primary bg-primary/10 text-primary" : "hover:bg-muted")}>
                {l.label}
              </button>
            ))}
          </div>
        </fieldset>

        {inCall ? (
          <Button size="lg" variant="destructive" className="w-full" onClick={hangUp} disabled={state === "connecting"}>
            <PhoneOff /> {state === "live" ? "End call" : "Cancel"}
          </Button>
        ) : (
          <Button size="lg" className="w-full" onClick={start}>
            <Mic /> {state === "ended" ? "Call again" : "Start test call"}
          </Button>
        )}

        <p className="mt-4 min-h-6 text-sm font-medium" aria-live="polite">
          {state === "connecting" && "Connecting…"}
          {state === "waiting" && "Connecting you to the receptionist…"}
          {state === "live" && (
            <>Connected. Speak any time. <span className="tabular-nums text-muted-foreground">
              {String(Math.floor(seconds / 60)).padStart(2, "0")}:{String(seconds % 60).padStart(2, "0")}
            </span></>
          )}
          {state === "ended" && !call && !message && "Call ended. Getting what it did…"}
          {message && <span className={state === "error" ? "text-destructive" : "text-muted-foreground"}>{message}</span>}
        </p>
        <div ref={audio} hidden />
      </section>

      {call && <AfterCall clinicId={clinicId} call={call} />}
      <TestCallsOnRecord clinicId={clinicId} onErased={() => { setCall(null); if (state === "ended") setState("idle"); }} />
    </div>
  );
}

function AfterCall({ clinicId, call }: { clinicId: number; call: ClinicCall }) {
  return (
    <section className="mx-auto max-w-md space-y-4 rounded-2xl border bg-card p-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-semibold">What this test call did</h2>
        <CallResult call={call} />
      </div>
      {call.changes.length ? (
        <ul className="space-y-1 text-sm">
          {call.changes.map((c) => (
            <li key={`${c.action}${c.appointment_id}`}>
              {changeText(c)}{c.starts_at && <span className="text-muted-foreground"> · {visitTime(c.starts_at)}</span>}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">It didn&apos;t book, move or cancel anything.</p>
      )}
      <Button variant="outline" asChild>
        <Link href={`/clinics/${clinicId}/calls/${call.id}`}>Read the conversation</Link>
      </Button>
    </section>
  );
}

/** While any test call is on record: how many, and one button to erase them all. */
function TestCallsOnRecord({ clinicId, onErased }: { clinicId: number; onErased: () => void }) {
  const tests = useTestCalls(clinicId);
  const erase = useEraseAllTestCalls(clinicId);
  if (!tests.data?.count) return null;
  const { count, erasable } = tests.data;
  const calls = (n: number) => `${n} test call${n === 1 ? "" : "s"}`;
  return (
    <section className="mx-auto flex max-w-md flex-wrap items-center justify-between gap-3 rounded-2xl border border-dashed bg-muted/40 p-5">
      <div className="text-sm">
        <p className="font-medium">{calls(count)} on record</p>
        <p className="text-muted-foreground">
          {erasable < count ? `${count - erasable === 1 ? "One is" : `${count - erasable} are`} still going: erase once it ends. ` : ""}
          Their bookings are real until you erase them.
        </p>
      </div>
      {erasable > 0 && (
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button variant="outline" className="text-destructive hover:text-destructive" disabled={erase.isPending}>
              <Eraser /> Erase {erasable === 1 ? "it" : `all ${erasable}`}
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Erase {calls(erasable)}?</AlertDialogTitle>
              <AlertDialogDescription>
                Every appointment they booked, moved or cancelled goes back to how it was, and their records and
                conversations are deleted. Patients&apos; calls aren&apos;t touched. This can&apos;t be undone.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Keep them</AlertDialogCancel>
              <AlertDialogAction onClick={() => erase.mutate(undefined, { onSuccess: onErased })}
                className="bg-destructive text-white hover:bg-destructive/90">
                Yes, erase {erasable === 1 ? "it" : "them"}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      )}
    </section>
  );
}
