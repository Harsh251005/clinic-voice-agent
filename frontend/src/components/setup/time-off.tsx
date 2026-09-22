"use client";
import { useState } from "react";
import { CalendarOff, Plus, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { todayIn } from "@/lib/dates";
import { useClinicChange } from "@/lib/queries";
import { Field } from "./field";
import { Section } from "./section";

const WHOLE_CLINIC = "clinic";

function span(from: string, to: string) {
  const fmt = (d: string) => new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" })
    .format(new Date(`${d}T00:00:00Z`));
  return from === to ? fmt(from) : `${fmt(from)} → ${fmt(to)}`;
}

export function TimeOff({ clinic }: { clinic: Schemas["Clinic"] }) {
  const today = todayIn(clinic.timezone);
  const [who, setWho] = useState(WHOLE_CLINIC);
  const [from, setFrom] = useState(today);
  const [to, setTo] = useState(today);
  const [reason, setReason] = useState("");
  const names = new Map(clinic.doctors.map((d) => [d.id, d.name]));
  const add = useClinicChange(clinic.id, (body: Schemas["TimeOffIn"]) =>
    unwrap(api.POST("/api/clinics/{clinic_id}/time-off", { params: { path: { clinic_id: clinic.id } }, body })),
    "Added. The receptionist won't offer those days.");
  const remove = useClinicChange(clinic.id, (id: number) =>
    unwrap(api.DELETE("/api/clinics/{clinic_id}/time-off/{time_off_id}", { params: { path: { clinic_id: clinic.id, time_off_id: id } } })),
    "Removed");

  return (
    <div className="space-y-6">
      <Section title="Upcoming leave and holidays" description="The receptionist tells callers about these and won't book on them.">
        {clinic.time_off.length === 0 ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <CalendarOff className="size-4" aria-hidden /> Nothing planned.
          </p>
        ) : (
          <ul className="divide-y">
            {clinic.time_off.map((t) => (
              <li key={t.id} className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
                <div className="flex flex-wrap items-center gap-2">
                  {t.doctor_id === null
                    ? <Badge className="bg-warning text-warning-foreground">Whole clinic</Badge>
                    : <Badge variant="secondary">{names.get(t.doctor_id) ?? "Doctor"}</Badge>}
                  <span className="font-medium">{span(t.date_from, t.date_to)}</span>
                  {t.reason && <span className="text-sm text-muted-foreground">{t.reason}</span>}
                </div>
                <Button variant="ghost" size="icon" aria-label="Remove" disabled={remove.isPending} onClick={() => remove.mutate(t.id)}>
                  <Trash2 />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Section>
      <Section title="Add leave or a holiday">
        <form className="grid gap-4 md:grid-cols-2" onSubmit={(e) => {
          e.preventDefault();
          add.mutate(
            { doctor_id: who === WHOLE_CLINIC ? null : Number(who), date_from: from, date_to: to, reason: reason.trim() },
            { onSuccess: () => setReason("") },
          );
        }}>
          <Field id="who" label="Who">
            <Select value={who} onValueChange={setWho}>
              <SelectTrigger id="who" className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value={WHOLE_CLINIC}>Whole clinic (holiday)</SelectItem>
                {clinic.doctors.map((d) => <SelectItem key={d.id} value={String(d.id)}>{d.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </Field>
          <Field id="reason" label="Reason (optional)">
            <Input id="reason" maxLength={200} placeholder="Diwali" value={reason} onChange={(e) => setReason(e.target.value)} />
          </Field>
          <Field id="from" label="From">
            <Input id="from" type="date" required value={from} onChange={(e) => { setFrom(e.target.value); if (e.target.value > to) setTo(e.target.value); }} />
          </Field>
          <Field id="to" label="To">
            <Input id="to" type="date" required min={from} value={to} onChange={(e) => setTo(e.target.value)} />
          </Field>
          <div className="flex justify-end md:col-span-2">
            <Button type="submit" disabled={add.isPending}><Plus /> Add</Button>
          </div>
        </form>
      </Section>
    </div>
  );
}
