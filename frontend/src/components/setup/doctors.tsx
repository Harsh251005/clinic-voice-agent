"use client";
import { useState } from "react";
import { Pencil, Plus, Power, Stethoscope } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { useClinicChange, usePatterns } from "@/lib/queries";
import { Field } from "./field";
import { Section } from "./section";

type Doctor = Schemas["Doctor"];
type DoctorFields = Omit<Schemas["NewDoctor"], "hours">;
const DEFAULT_PATTERN = "Mon–Sat, 10 am–1 pm and 5–8 pm";
const NO_HOURS = "No hours yet";

export function Doctors({ clinic }: { clinic: Schemas["Clinic"] }) {
  const [editing, setEditing] = useState<Doctor | null>(null);
  const path = (doctorId: number) => ({ params: { path: { clinic_id: clinic.id, doctor_id: doctorId } } });
  const update = useClinicChange(clinic.id, ({ id, body }: { id: number; body: Schemas["DoctorPatch"] }) =>
    unwrap(api.PATCH("/api/clinics/{clinic_id}/doctors/{doctor_id}", { ...path(id), body })),
    (d) => `${d.name} saved`);

  return (
    <div className="space-y-6">
      {clinic.doctors.length === 0 && (
        <Card><CardContent className="py-8 text-center text-muted-foreground">No doctors yet. Add the first one below.</CardContent></Card>
      )}
      <div className="grid gap-4 lg:grid-cols-2">
        {clinic.doctors.map((d) => (
          <Card key={d.id} className={d.active ? "" : "opacity-70"}>
            <CardContent className="space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className="grid size-10 place-items-center rounded-full bg-accent text-accent-foreground">
                    <Stethoscope className="size-5" aria-hidden />
                  </span>
                  <div>
                    <p className="font-semibold">{d.name}</p>
                    <p className="text-sm text-muted-foreground">{d.specialty || "No specialty"}</p>
                  </div>
                </div>
                {d.active ? <Badge className="bg-accent text-accent-foreground">Taking bookings</Badge> : <Badge variant="outline">Inactive</Badge>}
              </div>
              <div className="flex flex-wrap gap-1.5">
                <Badge variant="secondary">₹{d.fee}</Badge>
                <Badge variant="secondary">{d.slot_minutes} min slots</Badge>
              </div>
              <p className="text-sm text-muted-foreground">{d.hours_text}</p>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => setEditing(d)}><Pencil /> Edit</Button>
                <Button variant="ghost" size="sm" disabled={update.isPending}
                  onClick={() => update.mutate({ id: d.id, body: { active: !d.active } })}>
                  <Power /> {d.active ? "Deactivate" : "Activate"}
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
      <AddDoctor clinic={clinic} />
      <Dialog open={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit {editing?.name}</DialogTitle>
            <DialogDescription>Hours are on the Weekly hours tab.</DialogDescription>
          </DialogHeader>
          {editing && (
            <DoctorForm key={editing.id} initial={editing} submitLabel="Save doctor" pending={update.isPending}
              onSubmit={(body) => update.mutate({ id: editing.id, body }, { onSuccess: () => setEditing(null) })} />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function AddDoctor({ clinic }: { clinic: Schemas["Clinic"] }) {
  const patterns = usePatterns();
  const [start, setStart] = useState(DEFAULT_PATTERN);
  const [formKey, setFormKey] = useState(0);
  // Starting hours: the common patterns, a colleague's week, or none.
  const choices = new Map<string, Schemas["Sitting"][]>();
  for (const p of patterns.data ?? []) choices.set(p.name, p.sittings);
  for (const d of clinic.doctors) if (d.hours.length) choices.set(`Same as ${d.name}`, d.hours);
  choices.set(NO_HOURS, []);

  const add = useClinicChange(clinic.id, (body: Schemas["NewDoctor"]) =>
    unwrap(api.POST("/api/clinics/{clinic_id}/doctors", { params: { path: { clinic_id: clinic.id } }, body })),
    (d) => d.hours.length ? `${d.name} added with ${start}. Check them on the Weekly hours tab.` : `${d.name} added`);

  return (
    <Section title="Add a doctor"
      description="They start with the hours you pick here and are bookable right away, so check them on the Weekly hours tab.">
      <DoctorForm key={formKey} submitLabel="Add doctor" pending={add.isPending}
        extra={
          <Field id="starting" label="Starting hours" hint="Adjust them afterwards on the Weekly hours tab.">
            <Select value={start} onValueChange={setStart}>
              <SelectTrigger id="starting" className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>
                {[...choices.keys()].map((name) => <SelectItem key={name} value={name}>{name}</SelectItem>)}
              </SelectContent>
            </Select>
          </Field>
        }
        onSubmit={(fields) => add.mutate({ ...fields, hours: choices.get(start) ?? [] }, { onSuccess: () => setFormKey((k) => k + 1) })} />
    </Section>
  );
}

function DoctorForm({ initial, extra, submitLabel, pending, onSubmit }: {
  initial?: Doctor; extra?: React.ReactNode; submitLabel: string; pending: boolean; onSubmit: (fields: DoctorFields) => void;
}) {
  const [f, setF] = useState<DoctorFields>({
    name: initial?.name ?? "", specialty: initial?.specialty ?? "", fee: initial?.fee ?? 500, slot_minutes: initial?.slot_minutes ?? 15,
  });
  const set = (patch: Partial<DoctorFields>) => setF((x) => ({ ...x, ...patch }));
  const id = initial ? `doc${initial.id}` : "new";
  return (
    <form className="grid gap-4 md:grid-cols-2" onSubmit={(e) => { e.preventDefault(); onSubmit({ ...f, name: f.name.trim(), specialty: f.specialty?.trim() }); }}>
      <Field id={`${id}-name`} label="Name">
        <Input id={`${id}-name`} required maxLength={200} placeholder="Dr. Asha Mehta" value={f.name} onChange={(e) => set({ name: e.target.value })} />
      </Field>
      <Field id={`${id}-specialty`} label="Specialty">
        <Input id={`${id}-specialty`} maxLength={200} placeholder="General Physician" value={f.specialty} onChange={(e) => set({ specialty: e.target.value })} />
      </Field>
      <Field id={`${id}-fee`} label="Consultation fee (₹)">
        <Input id={`${id}-fee`} type="number" min={0} step={50} required value={f.fee} onChange={(e) => set({ fee: Number(e.target.value) })} />
      </Field>
      <Field id={`${id}-slot`} label="Slot length (minutes)">
        <Input id={`${id}-slot`} type="number" min={5} max={120} step={5} required value={f.slot_minutes} onChange={(e) => set({ slot_minutes: Number(e.target.value) })} />
      </Field>
      {extra && <div className="md:col-span-2">{extra}</div>}
      <DialogFooter className="md:col-span-2">
        <Button type="submit" disabled={pending}>{initial ? null : <Plus />} {submitLabel}</Button>
      </DialogFooter>
    </form>
  );
}
