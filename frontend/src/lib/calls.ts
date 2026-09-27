// A clinic's calls in the words its staff use: what happened, never how.
import type { Schemas } from "@/lib/api/client";
import { clockTime } from "@/lib/dates";

export type ClinicCall = Schemas["ClinicCall"];
type Change = Schemas["ClinicCallChange"];

const VERBS: Record<Change["action"], string> = { booked: "Booked", moved: "Moved", cancelled: "Cancelled" };

/** "Mon, 7 Dec, 10:00 am" from a naive clinic-local "2026-12-07T10:00:00". */
export function visitTime(naive: string): string {
  const day = new Intl.DateTimeFormat("en-IN", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" })
    .format(new Date(`${naive.slice(0, 10)}T00:00:00Z`));
  return `${day}, ${clockTime(naive)}`;
}

/** "Booked Riya Sharma with Dr. Asha Mehta" (the time is shown beside it). */
export function changeText(c: Change): string {
  if (!c.patient_name) return `${VERBS[c.action]} an appointment that has since been removed`;
  return `${VERBS[c.action]} ${c.patient_name} with ${c.doctor_name}`;
}

/** One line for a call with no appointment change. */
export function whatHappened(call: ClinicCall): string {
  if (call.status === "live") return "On the line now";
  if (call.status === "dropped") return "The call was cut off. The caller may not have been helped.";
  switch (call.outcome) {
    case "info_only": return "The caller asked a question";
    case "no_action": return "The caller didn't say anything";
    case "failed": return "Something went wrong. The caller may not have been helped.";
    default: return "No appointment changed";
  }
}
