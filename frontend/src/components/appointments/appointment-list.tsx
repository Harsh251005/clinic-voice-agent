"use client";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CalendarX2, Pencil, Phone, PhoneCall, TriangleAlert, UserRound } from "lucide-react";
import { toast } from "sonner";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { clockTime, longDay } from "@/lib/dates";
import { formatPhone } from "@/lib/phone";
import { keys } from "@/lib/queries";
import { cn } from "@/lib/utils";
import { AppointmentDialog } from "./appointment-form";

type Appointment = Schemas["Appointment"];

export function AppointmentList({ clinic, day, appointments }: { clinic: Schemas["Clinic"]; day: string; appointments: Appointment[] }) {
  if (!appointments.length) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-2 py-12 text-center">
          <CalendarX2 className="size-8 text-muted-foreground" aria-hidden />
          <p className="font-medium">No appointments on {longDay(day)}</p>
          <p className="text-sm text-muted-foreground">Bookings made on calls show up here. Add walk-ins and phone bookings with New appointment.</p>
        </CardContent>
      </Card>
    );
  }
  // A loop, not Map.groupBy: that needs Chrome 117+, and Next supports 111+.
  const byDoctor = new Map<string, Appointment[]>();
  const sorted = [...appointments].sort(
    (a, b) => a.doctor_name.localeCompare(b.doctor_name) || a.starts_at.localeCompare(b.starts_at),
  );
  for (const a of sorted) byDoctor.set(a.doctor_name, [...(byDoctor.get(a.doctor_name) ?? []), a]);
  return (
    <div className="space-y-4">
      {[...byDoctor].map(([doctor, rows]) => (
        <Card key={doctor} className="gap-0 py-0">
          <CardHeader className="border-b py-4">
            <CardTitle className="flex items-center justify-between text-base">
              {doctor}
              <span className="text-sm font-normal text-muted-foreground">
                {rows.filter((r) => r.status === "booked").length} booked
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="divide-y px-0">
            {rows.map((a) => <Row key={a.id} clinic={clinic} appt={a} />)}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function Row({ clinic, appt }: { clinic: Schemas["Clinic"]; appt: Appointment }) {
  const clinicId = clinic.id;
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const cancelled = appt.status === "cancelled";
  const cancel = useMutation({
    mutationFn: () =>
      unwrap(api.POST("/api/clinics/{clinic_id}/appointments/{appointment_id}/cancel", {
        params: { path: { clinic_id: clinicId, appointment_id: appt.id } },
      })),
    onSuccess: () => {
      toast.success(`Cancelled ${appt.patient_name}'s ${clockTime(appt.starts_at)} appointment. The slot is free again.`);
      return queryClient.invalidateQueries({ queryKey: keys.appointments(clinicId) });
    },
    onError: (err) => toast.error(err.message),
  });

  return (
    <div className={cn("flex flex-wrap items-center gap-x-4 gap-y-2 px-6 py-3", cancelled && "opacity-60")}>
      <p className="w-20 shrink-0 font-semibold tabular-nums">{clockTime(appt.starts_at)}</p>
      <div className="min-w-40 flex-1">
        <p className={cn("font-medium", cancelled && "line-through")}>{appt.patient_name}</p>
        <a href={`tel:${appt.patient_phone}`} className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <Phone className="size-3" aria-hidden /> {formatPhone(appt.patient_phone)}
        </a>
        {appt.reason && <p className="mt-0.5 text-sm text-foreground/80">{appt.reason}</p>}
      </div>
      <div className="flex items-center gap-1.5">
        {appt.source === "voice" ? (
          <Badge variant="secondary" className="bg-accent text-accent-foreground"><PhoneCall /> By receptionist</Badge>
        ) : (
          <Badge variant="outline"><UserRound /> By staff</Badge>
        )}
        {cancelled && <Badge className="bg-warning text-warning-foreground">Cancelled</Badge>}
      </div>
      {appt.problem && (
        <p className="flex basis-full items-center gap-1.5 rounded-md bg-warning px-2.5 py-1.5 text-sm text-warning-foreground order-last">
          <TriangleAlert className="size-4 shrink-0" aria-hidden />
          Call the patient: {appt.problem}.
        </p>
      )}
      <div className="flex w-40 justify-end gap-1">
        <Button variant="ghost" size="sm" className="text-muted-foreground" onClick={() => setEditing(true)}>
          <Pencil /> Edit
        </Button>
        <AppointmentDialog clinic={clinic} day={appt.starts_at.slice(0, 10)} editing={appt} open={editing} onOpenChange={setEditing} />
        {!cancelled && (
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-destructive" disabled={cancel.isPending}>
                Cancel
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Cancel {appt.patient_name}&apos;s appointment?</AlertDialogTitle>
                <AlertDialogDescription>
                  {clockTime(appt.starts_at)} with {appt.doctor_name}. The slot becomes free for other callers.
                  The patient isn&apos;t told automatically.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Keep it</AlertDialogCancel>
                <AlertDialogAction onClick={() => cancel.mutate()} className="bg-destructive text-white hover:bg-destructive/90">
                  Yes, cancel
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        )}
      </div>
    </div>
  );
}
