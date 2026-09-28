"use client";
import { CalendarDays, ChevronLeft, ChevronRight, Search, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Switch } from "@/components/ui/switch";
import { addDays, fromDate, longDay, toDate, weekdayOf } from "@/lib/dates";
import { cn } from "@/lib/utils";

export type View = "day" | "week";

/** Monday of the week the day is in: weeks run Monday to Sunday. */
export const weekStart = (day: string) => addDays(day, -weekdayOf(day));

function weekLabel(start: string) {
  const fmt = (day: string, opts: Intl.DateTimeFormatOptions) =>
    new Intl.DateTimeFormat("en-IN", { ...opts, timeZone: "UTC" }).format(new Date(`${day}T00:00:00Z`));
  const end = addDays(start, 6);
  return start.slice(5, 7) === end.slice(5, 7)
    ? `${fmt(start, { day: "numeric" })}–${fmt(end, { day: "numeric", month: "long" })}`
    : `${fmt(start, { day: "numeric", month: "short" })} – ${fmt(end, { day: "numeric", month: "short" })}`;
}

export function DiaryControls({
  view, day, today, showCancelled, search, onDay, onView, onShowCancelled, onSearch,
}: {
  view: View;
  day: string;
  today: string;
  showCancelled: boolean;
  search: string;
  onDay: (day: string) => void;
  onView: (view: View) => void;
  onShowCancelled: (show: boolean) => void;
  onSearch: (text: string) => void;
}) {
  const step = view === "week" ? 7 : 1;
  const unit = view === "week" ? "week" : "day";
  const onToday = view === "week" ? weekStart(day) === weekStart(today) : day === today;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-1.5">
          <Button variant="outline" size="icon" onClick={() => onDay(addDays(day, -step))} aria-label={`Previous ${unit}`}>
            <ChevronLeft />
          </Button>
          <Popover>
            <PopoverTrigger asChild>
              <Button variant="outline" className="min-w-52 justify-start font-medium">
                <CalendarDays /> {view === "week" ? weekLabel(weekStart(day)) : longDay(day)}
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0" align="start">
              <Calendar mode="single" selected={toDate(day)} defaultMonth={toDate(day)} weekStartsOn={1}
                onSelect={(d) => d && onDay(fromDate(d))} />
            </PopoverContent>
          </Popover>
          <Button variant="outline" size="icon" onClick={() => onDay(addDays(day, step))} aria-label={`Next ${unit}`}>
            <ChevronRight />
          </Button>
          {!onToday && <Button variant="ghost" onClick={() => onDay(today)}>Today</Button>}
        </div>
        <div className="inline-flex rounded-lg border bg-card p-0.5" role="group" aria-label="View">
          {([["day", "Day"], ["week", "Week"]] as const).map(([v, label]) => (
            <button key={v} type="button" aria-pressed={view === v} onClick={() => onView(v)}
              className={cn("min-h-9 rounded-md px-4 text-sm font-medium",
                view === v ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground")}>
              {label}
            </button>
          ))}
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="relative w-full sm:max-w-sm">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input type="search" value={search} onChange={(e) => onSearch(e.target.value)} className="h-10 pr-9 pl-9"
            placeholder="Find a patient: name or mobile" aria-label="Find a patient" />
          {search && (
            <button type="button" onClick={() => onSearch("")} aria-label="Clear search"
              className="absolute top-1/2 right-2 grid size-7 -translate-y-1/2 place-items-center rounded-md text-muted-foreground hover:text-foreground">
              <X className="size-4" />
            </button>
          )}
        </div>
        {view === "day" && !search && (
          <div className="flex items-center gap-2">
            <Switch id="show-cancelled" checked={showCancelled} onCheckedChange={onShowCancelled} />
            <Label htmlFor="show-cancelled" className="text-muted-foreground">Show cancelled</Label>
          </div>
        )}
      </div>
    </div>
  );
}
