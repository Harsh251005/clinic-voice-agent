"use client";
// What staff do to one appointment, from any view of the diary: mark the
// visit, edit, cancel (with Undo instead of an "are you sure?"), restore.
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Pencil, Phone, RotateCcw, X } from "lucide-react";
import { toast } from "sonner";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { clockTime, longDay } from "@/lib/dates";
import { formatPhone } from "@/lib/phone";
import { keys } from "@/lib/queries";
import { VISITS, visitInfo, type Visit } from "@/lib/visit";
import { AppointmentDialog } from "./appointment-form";

type Appointment = Schemas["Appointment"];

const UNDO_MS = 8_000;

export function useAppointmentActions(clinicId: number) {
  const queryClient = useQueryClient();
  const refresh = () => Promise.all([
    queryClient.invalidateQueries({ queryKey: keys.appointments(clinicId) }),
    queryClient.invalidateQueries({ queryKey: keys.clinic(clinicId) }), // doctors' upcoming counts
  ]);
  const path = (a: Appointment) => ({ params: { path: { clinic_id: clinicId, appointment_id: a.id } } });

  // A plain function, not a mutation: Undo lives in a toast that outlasts the
  // view it came from (a cancelled block leaves the grid).
  const restoreNow = async (a: Appointment) => {
    try {
      const back = await unwrap(api.POST("/api/clinics/{clinic_id}/appointments/{appointment_id}/restore", path(a)));
      toast.success(`${back.patient_name}'s ${clockTime(back.starts_at)} appointment is back on.`);
      await refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    }
  };
  const restore = useMutation({ mutationFn: restoreNow });

  const cancel = useMutation({
    mutationFn: (a: Appointment) =>
      unwrap(api.POST("/api/clinics/{clinic_id}/appointments/{appointment_id}/cancel", path(a))),
    onSuccess: (a) => {
      toast.success(`Cancelled ${a.patient_name}'s ${clockTime(a.starts_at)} appointment. The slot is free again.`, {
        duration: UNDO_MS,
        action: { label: "Undo", onClick: () => void restoreNow(a) },
      });
      return refresh();
    },
    onError: (err) => toast.error(err.message),
  });

  const visit = useMutation({
    mutationFn: ({ appt, visit }: { appt: Appointment; visit: Visit | null }) =>
      unwrap(api.POST("/api/clinics/{clinic_id}/appointments/{appointment_id}/visit", { ...path(appt), body: { visit } })),
    onSuccess: (a) => {
      const info = visitInfo(a.visit);
      toast.success(info ? `${a.patient_name}: ${info.label.toLowerCase()}.` : `${a.patient_name}: mark cleared.`);
      return refresh();
    },
    onError: (err) => toast.error(err.message),
  });

  return { cancel, restore, visit };
}

/** The menu behind an appointment: its trigger is whatever the view draws
 *  for the appointment (a grid block, a list row). */
export function AppointmentMenu({ clinic, appt, today, children }: {
  clinic: Schemas["Clinic"];
  appt: Appointment;
  today: string; // the clinic's date: visits can't be marked ahead of time
  children: React.ReactNode; // the trigger; must be a single button
}) {
  const { cancel, restore, visit } = useAppointmentActions(clinic.id);
  const [editing, setEditing] = useState(false);
  const booked = appt.status === "booked";
  const markable = booked && appt.starts_at.slice(0, 10) <= today;

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>{children}</DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-64">
          <DropdownMenuLabel className="space-y-0.5">
            <p className="font-semibold text-foreground">{appt.patient_name}</p>
            <p className="font-normal text-muted-foreground">
              {longDay(appt.starts_at.slice(0, 10))}, {clockTime(appt.starts_at)} · {appt.doctor_name}
            </p>
            {appt.reason && <p className="font-normal text-foreground/80">{appt.reason}</p>}
            {appt.problem && <p className="font-normal text-warning-foreground">Call the patient: {appt.problem}.</p>}
          </DropdownMenuLabel>
          <DropdownMenuItem asChild>
            <a href={`tel:${appt.patient_phone}`}><Phone /> Call {formatPhone(appt.patient_phone)}</a>
          </DropdownMenuItem>
          {markable && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuLabel className="text-xs font-medium text-muted-foreground">Visit</DropdownMenuLabel>
              {VISITS.map((v) => (
                <DropdownMenuItem key={v.value} disabled={visit.isPending}
                  onSelect={() => visit.mutate({ appt, visit: appt.visit === v.value ? null : v.value })}>
                  <v.icon /> {v.label}
                  {appt.visit === v.value && <Check className="ml-auto" aria-label="(marked)" />}
                </DropdownMenuItem>
              ))}
              {appt.visit && (
                <DropdownMenuItem onSelect={() => visit.mutate({ appt, visit: null })}>
                  <X /> Clear mark
                </DropdownMenuItem>
              )}
            </>
          )}
          <DropdownMenuSeparator />
          <DropdownMenuItem onSelect={() => setEditing(true)}><Pencil /> Edit</DropdownMenuItem>
          {booked ? (
            <DropdownMenuItem variant="destructive" disabled={cancel.isPending} onSelect={() => cancel.mutate(appt)}>
              <X /> Cancel appointment
            </DropdownMenuItem>
          ) : (
            <DropdownMenuItem disabled={restore.isPending} onSelect={() => restore.mutate(appt)}>
              <RotateCcw /> Restore appointment
            </DropdownMenuItem>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
      <AppointmentDialog clinic={clinic} day={appt.starts_at.slice(0, 10)} editing={appt} open={editing} onOpenChange={setEditing} />
    </>
  );
}

/** "Arrived", "By receptionist", "Cancelled": the words a block or row carries. */
export function statusWords(appt: Appointment): string[] {
  if (appt.status === "cancelled") return ["Cancelled"];
  const info = visitInfo(appt.visit);
  return [info?.label ?? "Booked", appt.source === "voice" ? "by receptionist" : "by staff"];
}
