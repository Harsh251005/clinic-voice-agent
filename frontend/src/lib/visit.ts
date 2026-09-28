// Visit marks: what happened at the clinic, set by staff. One vocabulary for
// every screen, always a word and an icon, never colour alone.
import { CircleCheck, CircleSlash, DoorOpen, type LucideIcon } from "lucide-react";
import type { Schemas } from "@/lib/api/client";

export type Visit = NonNullable<Schemas["Appointment"]["visit"]>;

export const VISITS: { value: Visit; label: string; icon: LucideIcon; tone: string }[] = [
  { value: "arrived", label: "Arrived", icon: DoorOpen, tone: "bg-primary text-primary-foreground" },
  { value: "done", label: "Done", icon: CircleCheck, tone: "bg-success text-success-foreground" },
  { value: "no_show", label: "No-show", icon: CircleSlash, tone: "bg-warning text-warning-foreground" },
];

export function visitInfo(visit: Visit | null | undefined) {
  return VISITS.find((v) => v.value === visit) ?? null;
}
