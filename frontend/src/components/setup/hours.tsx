"use client";
// Weekly hours: each day holds any number of sessions (none = closed), in
// any order of the day: evening-only is as easy as morning-only. Quick fills
// and per-day copies do the common cases; nothing is saved until Save.
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Copy, MessageSquareQuote, MoreHorizontal, Plus, TriangleAlert, Wand2, X } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { span12, time12 } from "@/lib/dates";
import { useClinicChange, usePatterns } from "@/lib/queries";
import { cn } from "@/lib/utils";
import { Section } from "./section";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const PRESETS = [
  { name: "Morning", start: "10:00", end: "13:00" },
  { name: "Afternoon", start: "14:00", end: "17:00" },
  { name: "Evening", start: "17:00", end: "20:00" },
] as const;
const COPIES = [
  { name: "Monday to Friday", days: [0, 1, 2, 3, 4] },
  { name: "Monday to Saturday", days: [0, 1, 2, 3, 4, 5] },
  { name: "every day", days: [0, 1, 2, 3, 4, 5, 6] },
];

type Sitting = Schemas["Sitting"];
/** One session being edited; `key` keeps inputs stable while times change. */
type Span = { key: number; start: string; end: string };
type Week = Span[][];

let nextKey = 0;
const makeSpan = (start: string, end: string): Span => ({ key: nextKey++, start, end });
const hhmm = (t: string) => t.slice(0, 5);
const byStart = (a: Span, b: Span) => a.start.localeCompare(b.start) || a.end.localeCompare(b.end);
const overlaps = (spans: Span[], start: string, end: string) => spans.some((s) => start < s.end && s.start < end);

function toWeek(sittings: Sitting[]): Week {
  return DAYS.map((_, day) => sittings.filter((s) => s.weekday === day)
    .map((s) => makeSpan(hhmm(s.start), hhmm(s.end))).sort(byStart));
}

function toSittings(week: Week): Sitting[] {
  return week.flatMap((spans, weekday) => [...spans].sort(byStart).map(({ start, end }) => ({ weekday, start, end })));
}

/** A free hour for "Other time": after the day's last session, else the first gap from 8 am. */
function freeHour(spans: Span[]): Span | undefined {
  const pad = (m: number) => `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
  const last = spans.reduce((m, s) => Math.max(m, Number(s.end.slice(0, 2)) * 60 + Number(s.end.slice(3))), 0);
  for (const from of [last, ...Array.from({ length: 29 }, (_, i) => 8 * 60 + i * 30)]) {
    if (from >= 8 * 60 && from + 60 < 24 * 60 && !overlaps(spans, pad(from), pad(from + 60))) {
      return makeSpan(pad(from), pad(from + 60));
    }
  }
}

/** The same checks the API makes, shown while typing. */
function problems(week: Week): string[] {
  return week.flatMap((spans, i) => {
    const out: string[] = [];
    const valid = [...spans].sort(byStart).filter((s) => {
      if (s.end > s.start) return true;
      out.push(`${DAYS[i]}: the session starting ${time12(s.start)} must end after it starts.`);
      return false;
    });
    for (let k = 1; k < valid.length; k++) {
      const [a, b] = [valid[k - 1], valid[k]];
      if (b.start < a.end) out.push(`${DAYS[i]}: ${span12(a.start, a.end)} and ${span12(b.start, b.end)} overlap.`);
    }
    return out;
  });
}

export function Hours({ clinic }: { clinic: Schemas["Clinic"] }) {
  const [doctorId, setDoctorId] = useState(clinic.doctors[0]?.id);
  const doctor = clinic.doctors.find((d) => d.id === doctorId) ?? clinic.doctors[0];
  if (!doctor) {
    return <Section title="Weekly hours"><p className="text-sm text-muted-foreground">Add a doctor first, on the Doctors tab.</p></Section>;
  }
  return (
    <div className="space-y-6">
      <div className="max-w-sm space-y-1.5">
        <Label htmlFor="hours-doctor">Doctor</Label>
        <Select value={String(doctor.id)} onValueChange={(v) => setDoctorId(Number(v))}>
          <SelectTrigger id="hours-doctor" className="w-full bg-card"><SelectValue /></SelectTrigger>
          <SelectContent>
            {clinic.doctors.map((d) => <SelectItem key={d.id} value={String(d.id)}>{d.name}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>
      {/* Keyed by doctor (and saved hours): switching doctors starts from their saved week. */}
      <WeekEditor key={`${doctor.id}:${JSON.stringify(doctor.hours)}`} clinic={clinic} doctor={doctor} />
    </div>
  );
}

function WeekEditor({ clinic, doctor }: { clinic: Schemas["Clinic"]; doctor: Schemas["Doctor"] }) {
  const saved = useMemo(() => toWeek(doctor.hours), [doctor.hours]);
  const [week, setWeek] = useState<Week>(saved);
  const [pattern, setPattern] = useState<string>("");
  const patterns = usePatterns();
  const sittings = toSittings(week);
  const dirty = JSON.stringify(sittings) !== JSON.stringify(toSittings(saved));
  const issues = problems(week);

  const fills = new Map<string, Sitting[]>();
  for (const p of patterns.data ?? []) fills.set(p.name, p.sittings);
  for (const d of clinic.doctors) if (d.id !== doctor.id && d.hours.length) fills.set(`Same as ${d.name}`, d.hours);

  const preview = useQuery({
    queryKey: ["hours-preview", sittings],
    queryFn: () => unwrap(api.POST("/api/hours/preview", { body: { sittings } })),
    enabled: issues.length === 0,
    placeholderData: (previous) => previous,
  });
  const save = useClinicChange(clinic.id, (body: Sitting[]) =>
    unwrap(api.PUT("/api/clinics/{clinic_id}/doctors/{doctor_id}/hours", {
      params: { path: { clinic_id: clinic.id, doctor_id: doctor.id } }, body: { sittings: body },
    })), `Hours saved for ${doctor.name}`);

  const setDay = (i: number, spans: Span[]) => setWeek((w) => w.map((d, j) => (j === i ? spans : d)));
  const copyDay = (i: number, days: number[]) => setWeek((w) =>
    w.map((d, j) => (j !== i && days.includes(j) ? w[i].map((s) => makeSpan(s.start, s.end)) : d)));

  return (
    <>
      <Section title="Fill the week" description="Start from a common pattern or a colleague's hours, then adjust single days below.">
        <div className="flex flex-col gap-2 md:flex-row">
          <Select value={pattern} onValueChange={setPattern}>
            <SelectTrigger className="w-full md:flex-1" aria-label="Pattern"><SelectValue placeholder="Choose a common pattern…" /></SelectTrigger>
            <SelectContent>
              {[...fills.keys()].map((name) => <SelectItem key={name} value={name}>{name}</SelectItem>)}
            </SelectContent>
          </Select>
          <Button variant="outline" disabled={!pattern} onClick={() => setWeek(toWeek(fills.get(pattern) ?? []))}>
            <Wand2 /> Apply
          </Button>
        </div>
      </Section>

      <Section title={`${doctor.name}'s week`}
        description="Add as many sessions a day as the doctor sits. A day with no sessions is closed."
        action={dirty ? <Badge className="bg-warning text-warning-foreground">Unsaved changes</Badge> : undefined}>
        <div className="divide-y">
          {week.map((spans, i) => (
            <DayRow key={DAYS[i]} day={i} spans={spans} onChange={(next) => setDay(i, next)} onCopy={(days) => copyDay(i, days)} />
          ))}
        </div>

        {issues.length > 0 ? (
          <Alert variant="destructive" className="mt-4">
            <TriangleAlert />
            <AlertDescription><ul className="list-disc pl-4">{issues.map((m, k) => <li key={k}>{m}</li>)}</ul></AlertDescription>
          </Alert>
        ) : (
          <p className="mt-4 flex items-start gap-2 rounded-lg bg-muted px-3 py-2.5 text-sm">
            <MessageSquareQuote className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
            <span>The receptionist will say: <b>{preview.data?.text ?? "…"}</b></span>
          </p>
        )}

        <div className="mt-5 flex justify-end gap-2">
          {dirty && <Button variant="ghost" onClick={() => setWeek(saved)}>Discard changes</Button>}
          <Button disabled={!dirty || issues.length > 0 || save.isPending} onClick={() => save.mutate(sittings)}>
            {save.isPending ? "Saving…" : "Save hours"}
          </Button>
        </div>
      </Section>
    </>
  );
}

function DayRow({ day, spans, onChange, onCopy }: {
  day: number; spans: Span[]; onChange: (spans: Span[]) => void; onCopy: (days: number[]) => void;
}) {
  const name = DAYS[day];
  const other = freeHour(spans);
  const add = (s: Span) => onChange([...spans, s].sort(byStart));
  const edit = (key: number, patch: Partial<Span>) => onChange(spans.map((s) => (s.key === key ? { ...s, ...patch } : s)));

  return (
    <div className="grid grid-cols-[1fr_auto] items-start gap-x-3 gap-y-2 py-3 md:grid-cols-[8rem_1fr_auto]">
      <span className={cn("flex min-h-[42px] items-center font-medium", !spans.length && "text-muted-foreground")}>{name}</span>

      <div className="col-span-2 row-start-2 flex min-h-[42px] flex-wrap items-center gap-2 md:col-span-1 md:col-start-2 md:row-start-1">
        {!spans.length && <span className="px-1 text-sm text-muted-foreground">Closed</span>}
        {spans.map((s, n) => (
          <div key={s.key} className="flex items-center gap-1 rounded-lg border bg-card p-1">
            <Time label={`${name} session ${n + 1} from`} value={s.start} onChange={(start) => edit(s.key, { start })} />
            <span className="text-xs text-muted-foreground">to</span>
            <Time label={`${name} session ${n + 1} to`} value={s.end} onChange={(end) => edit(s.key, { end })} />
            <Button variant="ghost" size="icon" className="size-8 text-muted-foreground"
              aria-label={`Remove ${name} session ${n + 1}`} onClick={() => onChange(spans.filter((x) => x.key !== s.key))}>
              <X />
            </Button>
          </div>
        ))}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" aria-label={`Add a session on ${name}`}><Plus /> Add</Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="min-w-56">
            {PRESETS.map((p) => (
              <DropdownMenuItem key={p.name} disabled={overlaps(spans, p.start, p.end)} onSelect={() => add(makeSpan(p.start, p.end))}>
                {p.name} <span className="ml-auto pl-4 whitespace-nowrap text-muted-foreground">{span12(p.start, p.end)}</span>
              </DropdownMenuItem>
            ))}
            <DropdownMenuSeparator />
            <DropdownMenuItem disabled={!other} onSelect={() => other && add(other)}>Other time</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <div className="col-start-2 row-start-1 flex min-h-[42px] items-center md:col-start-3">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" aria-label={`More for ${name}`}><MoreHorizontal /></Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {COPIES.map((c) => (
              <DropdownMenuItem key={c.name} onSelect={() => onCopy(c.days)}>
                <Copy /> Copy {name}&apos;s hours to {c.name}
              </DropdownMenuItem>
            ))}
            <DropdownMenuSeparator />
            <DropdownMenuItem variant="destructive" disabled={!spans.length} onSelect={() => onChange([])}>
              <X /> Mark {name} closed
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}

function Time({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <Input type="time" step={900} aria-label={label} value={value}
      className="h-8 w-[7.25rem] border-0 tabular-nums shadow-none" onChange={(e) => e.target.value && onChange(e.target.value)} />
  );
}
