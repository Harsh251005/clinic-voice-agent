"use client";
// One form for booking and for changing a booking: doctor, day, time, who
// and why. Staff have the final say, so any time can be typed; the doctor's
// free times are offered as quick picks. The API refuses only a double booking.
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { Field } from "@/components/setup/field";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { clockTime, longDay } from "@/lib/dates";
import { keys } from "@/lib/queries";
import { cn } from "@/lib/utils";

type Appointment = Schemas["Appointment"];
type Form = { doctor: string; day: string; time: string; name: string; phone: string; reason: string };

export function AppointmentDialog({ clinic, day, editing, open, onOpenChange }: {
  clinic: Schemas["Clinic"];
  day: string;
  editing?: Appointment; // absent = a new booking
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{editing ? `Change ${editing.patient_name}'s appointment` : "New appointment"}</DialogTitle>
          <DialogDescription>
            {editing
              ? "Change anything: the doctor, day, time, the patient's details or the reason. The patient isn't told automatically."
              : "For walk-ins and bookings taken on the clinic's own phone. The receptionist won't offer this time to callers."}
          </DialogDescription>
        </DialogHeader>
        {open && (
          <AppointmentForm key={editing?.id ?? "new"} clinic={clinic} day={day} editing={editing} onDone={() => onOpenChange(false)} />
        )}
      </DialogContent>
    </Dialog>
  );
}

function AppointmentForm({ clinic, day, editing, onDone }: {
  clinic: Schemas["Clinic"]; day: string; editing?: Appointment; onDone: () => void;
}) {
  const queryClient = useQueryClient();
  // Doctors taking bookings first; an inactive one only if this booking is theirs.
  const doctors = clinic.doctors.filter((d) => d.active || d.id === editing?.doctor_id);
  const [f, setF] = useState<Form>(() => ({
    doctor: String(editing?.doctor_id ?? doctors[0]?.id ?? ""),
    day: editing?.starts_at.slice(0, 10) ?? day,
    time: editing?.starts_at.slice(11, 16) ?? "",
    name: editing?.patient_name ?? "",
    phone: editing?.patient_phone ?? "",
    reason: editing?.reason ?? "",
  }));
  const set = (patch: Partial<Form>) => setF((x) => ({ ...x, ...patch }));

  const free = useQuery({
    queryKey: [...keys.appointments(clinic.id), "free", f.doctor, f.day],
    queryFn: () => unwrap(api.GET("/api/clinics/{clinic_id}/doctors/{doctor_id}/free", {
      params: { path: { clinic_id: clinic.id, doctor_id: Number(f.doctor) }, query: { day: f.day } },
    })),
    enabled: !!f.doctor && !!f.day,
  });
  const picks = (free.data?.times ?? []).map((t) => t.slice(0, 5));
  // A new booking starts on the first free time; typing or picking replaces it.
  const time = f.time || (editing ? "" : picks[0] ?? "");

  const save = useMutation({
    mutationFn: () => {
      const body: Schemas["AppointmentIn"] = {
        doctor_id: Number(f.doctor), starts_at: `${f.day}T${time}:00`,
        patient_name: f.name.trim(), patient_phone: f.phone.trim(), reason: f.reason.trim(),
      };
      return editing
        ? unwrap(api.PUT("/api/clinics/{clinic_id}/appointments/{appointment_id}", {
          params: { path: { clinic_id: clinic.id, appointment_id: editing.id } }, body,
        }))
        : unwrap(api.POST("/api/clinics/{clinic_id}/appointments", { params: { path: { clinic_id: clinic.id } }, body }));
    },
    onSuccess: (a) => {
      toast.success(`${editing ? "Saved" : "Booked"}: ${a.patient_name} with ${a.doctor_name}, ${longDay(a.starts_at.slice(0, 10))} at ${clockTime(a.starts_at)}.`);
      onDone();
      return Promise.all([
        queryClient.invalidateQueries({ queryKey: keys.appointments(clinic.id) }),
        queryClient.invalidateQueries({ queryKey: keys.clinic(clinic.id) }), // doctors' upcoming counts
      ]);
    },
    onError: (err) => toast.error(err.message),
  });

  if (!doctors.length) {
    return <p className="text-sm text-muted-foreground">Add a doctor on the Clinic setup page first.</p>;
  }
  return (
    <form className="grid gap-4 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
      <Field id="appt-doctor" label="Doctor">
        <Select value={f.doctor} onValueChange={(doctor) => set({ doctor })}>
          <SelectTrigger id="appt-doctor" className="w-full"><SelectValue /></SelectTrigger>
          <SelectContent>
            {doctors.map((d) => (
              <SelectItem key={d.id} value={String(d.id)}>{d.name}{d.active ? "" : " (inactive)"}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>
      <Field id="appt-day" label="Day">
        <Input id="appt-day" type="date" required value={f.day} onChange={(e) => set({ day: e.target.value })} />
      </Field>
      <div className="space-y-2 sm:col-span-2">
        <Field id="appt-time" label="Time" hint="Pick a free time, or type any time: you can book outside hours or squeeze a walk-in in.">
          <Input id="appt-time" type="time" required className="w-40" value={time} onChange={(e) => set({ time: e.target.value })} />
        </Field>
        {free.isLoading ? <Skeleton className="h-8 w-full" /> : picks.length ? (
          <div className="flex flex-wrap gap-1.5" aria-label="Free times">
            {picks.map((t) => (
              <Button key={t} type="button" size="sm" variant={time === t ? "default" : "outline"}
                className={cn("tabular-nums", time !== t && "text-muted-foreground")} onClick={() => set({ time: t })}>
                {clockTime(`${f.day}T${t}`)}
              </Button>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No free times that day by the doctor&apos;s hours. You can still type a time.</p>
        )}
      </div>
      <Field id="appt-name" label="Patient name">
        <Input id="appt-name" required maxLength={200} placeholder="Meena Joshi" value={f.name} onChange={(e) => set({ name: e.target.value })} />
      </Field>
      <Field id="appt-phone" label="Mobile number">
        <Input id="appt-phone" required inputMode="tel" maxLength={20} placeholder="98190 22222" value={f.phone} onChange={(e) => set({ phone: e.target.value })} />
      </Field>
      <div className="sm:col-span-2">
        <Field id="appt-reason" label="Reason for visit (optional)">
          <Textarea id="appt-reason" rows={2} maxLength={300} placeholder="Blurred vision for a week" value={f.reason}
            onChange={(e) => set({ reason: e.target.value })} />
        </Field>
      </div>
      <DialogFooter className="sm:col-span-2">
        <Button type="submit" disabled={save.isPending || !time}>{editing ? "Save changes" : "Book appointment"}</Button>
      </DialogFooter>
    </form>
  );
}
