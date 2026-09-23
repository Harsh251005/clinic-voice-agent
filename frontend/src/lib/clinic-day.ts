// What a clinic's day looks like from its data: who is in, whether the
// clinic is open right now, and what's still missing from its setup.
// Pure functions over API data; times are naive clinic-local "HH:MM".
import type { Schemas } from "@/lib/api/client";
import { weekdayOf } from "@/lib/dates";

type Clinic = Schemas["Clinic"];
type Doctor = Schemas["Doctor"];

export type DoctorToday =
  | { kind: "in"; sittings: { start: string; end: string }[] }
  | { kind: "leave"; reason: string }
  | { kind: "off" };

function covers(t: Schemas["TimeOff"], day: string) {
  return t.date_from <= day && day <= t.date_to;
}

export function clinicHoliday(clinic: Clinic, day: string): Schemas["TimeOff"] | undefined {
  return clinic.time_off.find((t) => t.doctor_id === null && covers(t, day));
}

export function doctorToday(clinic: Clinic, doctor: Doctor, day: string): DoctorToday {
  const leave = clinic.time_off.find((t) => t.doctor_id === doctor.id && covers(t, day)) ?? clinicHoliday(clinic, day);
  if (leave) return { kind: "leave", reason: leave.reason };
  const weekday = weekdayOf(day);
  const sittings = doctor.hours
    .filter((h) => h.weekday === weekday)
    .map((h) => ({ start: h.start.slice(0, 5), end: h.end.slice(0, 5) }))
    .sort((a, b) => a.start.localeCompare(b.start));
  return sittings.length ? { kind: "in", sittings } : { kind: "off" };
}

export type OpenState =
  | { kind: "open"; until: string }
  | { kind: "opens"; at: string }
  | { kind: "closed-today"; reason?: string }
  | { kind: "done" };

/** Open while any doctor who's in is sitting. `now` is "HH:MM" at the clinic. */
export function openState(clinic: Clinic, day: string, now: string): OpenState {
  const holiday = clinicHoliday(clinic, day);
  if (holiday) return { kind: "closed-today", reason: holiday.reason || undefined };
  const sittings = clinic.doctors
    .filter((d) => d.active)
    .flatMap((d) => {
      const today = doctorToday(clinic, d, day);
      return today.kind === "in" ? today.sittings : [];
    })
    .sort((a, b) => a.start.localeCompare(b.start));
  if (!sittings.length) return { kind: "closed-today" };

  // Merge overlapping sittings into the clinic's own open blocks.
  const blocks: { start: string; end: string }[] = [];
  for (const s of sittings) {
    const last = blocks.at(-1);
    if (last && s.start <= last.end) last.end = s.end > last.end ? s.end : last.end;
    else blocks.push({ ...s });
  }
  const current = blocks.find((b) => b.start <= now && now < b.end);
  if (current) return { kind: "open", until: current.end };
  const next = blocks.find((b) => b.start > now);
  return next ? { kind: "opens", at: next.start } : { kind: "done" };
}

export type SetupStep = { id: string; label: string; hint: string; done: boolean; tab: string };

/** What the receptionist needs before it can answer callers well. */
export function setupSteps(clinic: Clinic): SetupStep[] {
  const active = clinic.doctors.filter((d) => d.active);
  return [
    {
      id: "details", tab: "clinic", done: !!clinic.address.trim() && !!clinic.phone.trim(),
      label: "Add your clinic's address and phone",
      hint: "Callers ask where you are more than anything else.",
    },
    {
      id: "doctors", tab: "doctors", done: active.length > 0,
      label: "Add your doctors",
      hint: "With their fee and how long each patient takes.",
    },
    {
      id: "hours", tab: "hours", done: active.length > 0 && active.every((d) => d.hours.length > 0),
      label: "Set every doctor's weekly hours",
      hint: "The receptionist only books inside these hours.",
    },
    {
      id: "faq", tab: "faq", done: clinic.faq.length > 0,
      label: "Answer common questions",
      hint: "Parking, payment, reports: anything patients often ask.",
    },
  ];
}
