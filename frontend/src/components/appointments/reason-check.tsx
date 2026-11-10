// The receptionist booked but couldn't tell whether the visit reason fits the
// doctor's specialty: the clinic checks it (a clear mismatch is never booked).
import { SearchCheck } from "lucide-react";
import { cn } from "@/lib/utils";

export const REASON_CHECK_HELP = "The receptionist wasn't sure this doctor sees this. Please check with the patient.";

/** "Check reason", beside the reason wherever an appointment is listed. */
export function ReasonCheckTag({ className }: { className?: string }) {
  return (
    <span title={REASON_CHECK_HELP}
      className={cn("inline-flex items-center gap-1 rounded bg-warning px-1.5 py-px text-[11px] font-semibold tracking-wide text-warning-foreground uppercase", className)}>
      <SearchCheck className="size-3" aria-hidden /> Check reason
    </span>
  );
}
