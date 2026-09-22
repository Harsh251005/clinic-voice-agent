import { Card, CardContent } from "@/components/ui/card";

export function Stats({ booked, onCalls, week }: { booked: number; onCalls: number; week: number }) {
  const items = [
    { label: "Booked this day", value: booked },
    { label: "Booked on calls", value: onCalls, hint: "by the receptionist" },
    { label: "Next 7 days", value: week, hint: "from this day" },
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
