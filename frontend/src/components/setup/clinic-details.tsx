"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { useClinicChange } from "@/lib/queries";
import { Field } from "./field";
import { Section } from "./section";

type Details = Schemas["ClinicDetails"];

export function ClinicDetails({ clinic }: { clinic: Schemas["Clinic"] }) {
  const saved: Details = {
    name: clinic.name, address: clinic.address, phone: clinic.phone,
    booking_window_days: clinic.booking_window_days, slots_offered: clinic.slots_offered,
  };
  const [form, setForm] = useState<Details>(saved);
  const set = (patch: Partial<Details>) => setForm((f) => ({ ...f, ...patch }));
  const dirty = JSON.stringify(form) !== JSON.stringify(saved);
  const save = useClinicChange(clinic.id, (body: Details) =>
    unwrap(api.PATCH("/api/clinics/{clinic_id}", { params: { path: { clinic_id: clinic.id } }, body })),
    "Clinic details saved",
  );

  return (
    <form
      className="space-y-6"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate(form);
      }}
    >
      <Section title="Clinic details" description="The receptionist introduces the clinic with its name, and gives the address and phone when asked.">
        <div className="grid gap-4 md:grid-cols-2">
          <Field id="name" label="Clinic name">
            <Input id="name" required maxLength={200} value={form.name} onChange={(e) => set({ name: e.target.value })} />
          </Field>
          <Field id="phone" label="Phone">
            <Input id="phone" maxLength={20} inputMode="tel" value={form.phone} onChange={(e) => set({ phone: e.target.value })} />
          </Field>
          <div className="md:col-span-2">
            <Field id="address" label="Address">
              <Textarea id="address" rows={2} maxLength={500} value={form.address} onChange={(e) => set({ address: e.target.value })} />
            </Field>
          </div>
        </div>
      </Section>
      <Section title="Booking rules">
        <div className="grid gap-4 md:grid-cols-2">
          <Field id="window" label="Book up to (days ahead)" hint="Callers can't book further out than this.">
            <Input id="window" type="number" min={1} max={365} required value={form.booking_window_days}
              onChange={(e) => set({ booking_window_days: Number(e.target.value) })} />
          </Field>
          <Field id="offered" label="Free times offered at once" hint="How many free times the receptionist reads out in one go.">
            <Input id="offered" type="number" min={1} max={6} required value={form.slots_offered}
              onChange={(e) => set({ slots_offered: Number(e.target.value) })} />
          </Field>
        </div>
      </Section>
      <div className="flex justify-end gap-2">
        {dirty && <Button type="button" variant="ghost" onClick={() => setForm(saved)}>Discard changes</Button>}
        <Button type="submit" disabled={!dirty || save.isPending}>{save.isPending ? "Saving…" : "Save details"}</Button>
      </div>
    </form>
  );
}
