"use client";
// Weekly hours: one row per day, up to two sittings (a morning and an
// evening, say). Quick fills do the common cases; nothing is saved until Save.
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Copy, MessageSquareQuote, TriangleAlert, Wand2 } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { useClinicChange, usePatterns } from "@/lib/queries";
import { cn } from "@/lib/utils";
import { Section } from "./section";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const MORNING = ["10:00", "13:00"] as const;
const EVENING = ["17:00", "20:00"] as const;

type Sitting = Schemas["Sitting"];
type Day = { open: boolean; s1: string; e1: string; two: boolean; s2: string; e2: string };

const hhmm = (t: string) => t.slice(0, 5);

function toWeek(sittings: Sitting[]): Day[] {
  return DAYS.map((_, day) => {
    const spans = sittings.filter((s) => s.weekday === day).map((s) => [hhmm(s.start), hhmm(s.end)]).sort();
    const [first, second] = [spans[0] ?? MORNING, spans[1] ?? EVENING];
    return { open: spans.length > 0, s1: first[0], e1: first[1], two: spans.length > 1, s2: second[0], e2: second[1] };
  });
}

function toSittings(week: Day[]): Sitting[] {
  return week.flatMap((d, weekday) => !d.open ? [] : [
    { weekday, start: d.s1, end: d.e1 },
    ...(d.two ? [{ weekday, start: d.s2, end: d.e2 }] : []),
  ]);
}

/** The same checks the API makes, shown while typing. */
function problems(week: Day[]): string[] {
  return week.flatMap((d, i) => {
    if (!d.open) return [];
    const out: string[] = [];
    if (d.e1 <= d.s1) out.push(`${DAYS[i]}: the sitting must end after it starts.`);
    if (d.two && d.e2 <= d.s2) out.push(`${DAYS[i]}: the second sitting must end after it starts.`);
    else if (d.two && d.s2 < d.e1) out.push(`${DAYS[i]}: the second sitting starts before the first one ends.`);
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
  const [week, setWeek] = useState<Day[]>(saved);
  const [pattern, setPattern] = useState<string>("");
  const patterns = usePatterns();
  const sittings = toSittings(week);
  const dirty = JSON.stringify(week) !== JSON.stringify(saved);
  const issues = problems(week);
  const extra = DAYS.some((_, i) => doctor.hours.filter((h) => h.weekday === i).length > 2);

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

  const setDay = (i: number, patch: Partial<Day>) => setWeek((w) => w.map((d, j) => (j === i ? { ...d, ...patch } : d)));
  const copyMonday = () => setWeek((w) => w.map((d, i) => (i === 0 || !d.open ? d : { ...w[0], open: true })));

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
          <Button variant="outline" onClick={copyMonday}><Copy /> Copy Monday to all open days</Button>
        </div>
      </Section>

      <Section title={`${doctor.name}'s week`}
        action={dirty ? <Badge className="bg-warning text-warning-foreground">Unsaved changes</Badge> : undefined}>
        {extra && (
          <Alert className="mb-4"><TriangleAlert /><AlertDescription>Some days have more than two sittings. This table shows and saves the first two.</AlertDescription></Alert>
        )}
        <div className="hidden grid-cols-[8rem_4rem_1fr_1fr_7rem_1fr_1fr] gap-3 pb-2 text-xs font-medium text-muted-foreground md:grid">
          <span>Day</span><span>Open</span><span>From</span><span>To</span><span>Second sitting</span><span>From</span><span>To</span>
        </div>
        <div className="divide-y md:divide-y-0">
          {week.map((d, i) => (
            <div key={DAYS[i]} className="grid grid-cols-2 items-center gap-x-3 gap-y-2 py-3 md:grid-cols-[8rem_4rem_1fr_1fr_7rem_1fr_1fr] md:py-1.5">
              <span className={cn("font-medium", !d.open && "text-muted-foreground")}>{DAYS[i]}</span>
              <div className="justify-self-end md:justify-self-start">
                <Switch checked={d.open} onCheckedChange={(open) => setDay(i, { open })} aria-label={`${DAYS[i]} open`} />
              </div>
              <Time label={`${DAYS[i]} from`} value={d.s1} disabled={!d.open} onChange={(s1) => setDay(i, { s1 })} />
              <Time label={`${DAYS[i]} to`} value={d.e1} disabled={!d.open} onChange={(e1) => setDay(i, { e1 })} />
              <div className="col-span-2 flex items-center gap-2 md:col-span-1">
                <Switch checked={d.two} disabled={!d.open} onCheckedChange={(two) => setDay(i, { two })} aria-label={`${DAYS[i]} second sitting`} />
                <span className="text-sm text-muted-foreground md:hidden">Second sitting</span>
              </div>
              <Time label={`${DAYS[i]} second from`} value={d.s2} disabled={!d.open || !d.two} onChange={(s2) => setDay(i, { s2 })}
                hidden={!d.open || !d.two} />
              <Time label={`${DAYS[i]} second to`} value={d.e2} disabled={!d.open || !d.two} onChange={(e2) => setDay(i, { e2 })}
                hidden={!d.open || !d.two} />
            </div>
          ))}
        </div>

        {issues.length > 0 ? (
          <Alert variant="destructive" className="mt-4">
            <TriangleAlert />
            <AlertDescription><ul className="list-disc pl-4">{issues.map((m) => <li key={m}>{m}</li>)}</ul></AlertDescription>
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

function Time({ label, value, disabled, hidden, onChange }: {
  label: string; value: string; disabled: boolean; hidden?: boolean; onChange: (v: string) => void;
}) {
  return (
    <Input type="time" step={900} aria-label={label} value={value} disabled={disabled}
      className={cn("tabular-nums", hidden && "max-md:hidden")} onChange={(e) => e.target.value && onChange(e.target.value)} />
  );
}
