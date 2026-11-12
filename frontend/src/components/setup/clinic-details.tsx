"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { useClinicChange } from "@/lib/queries";
import { Field } from "./field";
import { HindiNameField } from "./hindi-name";
import { Section } from "./section";

type Details = Schemas["ClinicDetails"];

export function ClinicDetails({ clinic }: { clinic: Schemas["Clinic"] }) {
  const saved: Details = {
    name: clinic.name, name_hi: clinic.name_hi, address: clinic.address, phone: clinic.phone,
    directions: clinic.directions, booking_window_days: clinic.booking_window_days,
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
        // The API may write the Hindi name itself (left blank, or the clinic renamed): show what it saved.
        save.mutate(form, { onSuccess: (c) => set({ name_hi: c.name_hi }) });
      }}
    >
      <Section title="Clinic details" description="The receptionist introduces the clinic with its name, and gives the address and phone when asked.">
        <div className="grid gap-4 md:grid-cols-2">
          <Field id="name" label="Clinic name">
            <Input id="name" required maxLength={200} value={form.name} onChange={(e) => set({ name: e.target.value })} />
          </Field>
          <HindiNameField id="name-hi" label="Clinic name in Hindi" clinicId={clinic.id} english={form.name}
            value={form.name_hi ?? ""} onChange={(name_hi) => set({ name_hi })} placeholder="डेमो फ़ैमिली क्लिनिक" />
          <Field id="phone" label="Phone">
            <Input id="phone" maxLength={20} inputMode="tel" value={form.phone} onChange={(e) => set({ phone: e.target.value })} />
          </Field>
          <div className="md:col-span-2">
            <Field id="address" label="Address">
              <Textarea id="address" rows={2} maxLength={500} value={form.address} onChange={(e) => set({ address: e.target.value })} />
            </Field>
          </div>
          <div className="md:col-span-2">
            <Field id="directions" label="How to find the clinic"
              hint="What she says when a caller asks the way, instead of reading out the postal address. A landmark works best.">
              <Textarea id="directions" rows={2} maxLength={300} value={form.directions ?? ""}
                placeholder="Near Borivali East station, opposite the HDFC bank, first floor."
                onChange={(e) => set({ directions: e.target.value })} />
            </Field>
          </div>
        </div>
      </Section>
      <Section title="Booking rules">
        <div className="max-w-xs">
          <Field id="window" label="Book up to (days ahead)" hint="Callers can't book further out than this.">
            <Input id="window" type="number" min={1} max={365} required value={form.booking_window_days}
              onChange={(e) => set({ booking_window_days: Number(e.target.value) })} />
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
