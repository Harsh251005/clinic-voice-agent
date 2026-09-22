"use client";
import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Switch } from "@/components/ui/switch";
import { addDays, fromDate, longDay, toDate } from "@/lib/dates";

export function DayControls({
  day, today, showCancelled, onDay, onShowCancelled,
}: {
  day: string;
  today: string;
  showCancelled: boolean;
  onDay: (day: string) => void;
  onShowCancelled: (show: boolean) => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-center gap-1.5">
        <Button variant="outline" size="icon" onClick={() => onDay(addDays(day, -1))} aria-label="Previous day">
          <ChevronLeft />
        </Button>
        <Popover>
          <PopoverTrigger asChild>
            <Button variant="outline" className="min-w-52 justify-start font-medium">
              <CalendarDays /> {longDay(day)}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-auto p-0" align="start">
            <Calendar mode="single" selected={toDate(day)} defaultMonth={toDate(day)}
              onSelect={(d) => d && onDay(fromDate(d))} />
          </PopoverContent>
        </Popover>
        <Button variant="outline" size="icon" onClick={() => onDay(addDays(day, 1))} aria-label="Next day">
          <ChevronRight />
        </Button>
        {day !== today && <Button variant="ghost" onClick={() => onDay(today)}>Today</Button>}
      </div>
      <div className="flex items-center gap-2">
        <Switch id="show-cancelled" checked={showCancelled} onCheckedChange={onShowCancelled} />
        <Label htmlFor="show-cancelled" className="text-muted-foreground">Show cancelled</Label>
      </div>
    </div>
  );
}
