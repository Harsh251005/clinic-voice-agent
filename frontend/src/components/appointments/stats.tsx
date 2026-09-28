import { Card, CardContent } from "@/components/ui/card";
import type { Schemas } from "@/lib/api/client";

export function Stats({ day }: { day: Schemas["Day"] }) {
  const booked = day.appointments.filter((a) => a.status === "booked");
  const count = (visit: string) => booked.filter((a) => a.visit === visit).length;
  const seen = [[count("arrived"), "arrived"], [count("done"), "done"], [count("no_show"), "no-show"]]
    .filter(([n]) => n).map(([n, word]) => `${n} ${word}`).join(" · ");
  const items = [
    { label: "Booked this day", value: day.booked, hint: seen || undefined },
    { label: "Booked by receptionist", value: day.booked_on_calls, hint: "from calls" },
    { label: "Next 7 days", value: day.next_7_days, hint: "from this day" },
  ];
  return (
    <div className="grid grid-cols-3 gap-3">
      {items.map(({ label, value, hint }) => (
        <Card key={label} className="py-4">
          <CardContent className="px-4">
            <p className="text-xs font-medium text-muted-foreground sm:text-sm">{label}</p>
            <p className="mt-1 text-2xl font-semibold tabular-nums text-primary sm:text-3xl">{value}</p>
            {hint && <p className="mt-0.5 hidden text-xs text-muted-foreground sm:block">{hint}</p>}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
