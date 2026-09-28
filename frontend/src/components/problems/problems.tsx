"use client";
// Problems, impossible to miss: a banner on every page (red can't be put
// away while it lasts), a bell with the list, and, while something is
// wrong, a "(!)" in the browser tab and desktop alerts. The same pieces
// serve the clinic (plain words) and the operator (technical words): the
// API writes the words.
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell, BellRing, CircleCheck, Info, OctagonAlert, TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { Schemas } from "@/lib/api/client";
import { cn } from "@/lib/utils";

type Problem = Schemas["Problem"];

const SHOWN = 3; // banners before "and N more in the bell"

const TONE = {
  critical: { icon: OctagonAlert, banner: "border-destructive bg-destructive text-white", dot: "bg-destructive", word: "Urgent" },
  warning: { icon: TriangleAlert, banner: "border-warning-foreground/30 bg-warning text-warning-foreground", dot: "bg-amber-500", word: "Needs attention" },
  info: { icon: Info, banner: "border-border bg-secondary text-secondary-foreground", dot: "bg-muted-foreground", word: "Note" },
} as const;

/** "since 10:42 am" today, "since 27 Sept, 10:42 am" before. Browser time: these are UTC instants. */
function since(iso: string) {
  const at = new Date(iso);
  const time = at.toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" });
  const today = at.toDateString() === new Date().toDateString();
  return today ? `since ${time}` : `since ${at.toLocaleDateString("en-IN", { day: "numeric", month: "short" })}, ${time}`;
}

/** What goes in the banner: every urgent problem, and the rest until marked seen. */
function bannered(open: Problem[]) {
  return open.filter((p) => p.severity === "critical" || !p.seen);
}

export function ProblemBanner({ open, onSeen, seenPending }: {
  open: Problem[];
  onSeen: (id: number) => void;
  seenPending?: boolean;
}) {
  const shown = bannered(open);
  if (!shown.length) return null;
  const rest = shown.length - SHOWN;
  return (
    <div className="mb-6 space-y-2" aria-label="Problems">
      {shown.slice(0, SHOWN).map((p) => {
        const tone = TONE[p.severity];
        return (
          <div key={p.id} role={p.severity === "critical" ? "alert" : "status"}
            className={cn("flex flex-wrap items-start gap-x-3 gap-y-2 rounded-xl border px-4 py-3", tone.banner,
              p.severity === "critical" && "shadow-md")}>
            <tone.icon className="mt-0.5 size-5 shrink-0" aria-hidden />
            <div className="min-w-0 flex-1 basis-60">
              <p className="font-semibold">
                <span className="sr-only">{tone.word}: </span>{p.title}
              </p>
              <p className="text-sm opacity-90">
                {p.action}{p.action && " "}
                <span className="whitespace-nowrap opacity-80">({since(p.since)})</span>
              </p>
            </div>
            <div className="flex shrink-0 gap-2">
              {p.link && (
                <Button asChild size="sm" variant={p.severity === "critical" ? "secondary" : "outline"}
                  className={cn(p.severity !== "critical" && "border-current/30 bg-transparent")}>
                  <Link href={p.link}>Open</Link>
                </Button>
              )}
              {p.severity !== "critical" && (
                <Button size="sm" variant="ghost" disabled={seenPending} onClick={() => onSeen(p.id)}
                  className="hover:bg-black/5">
                  Seen
                </Button>
              )}
            </div>
          </div>
        );
      })}
      {rest > 0 && <p className="px-1 text-sm text-muted-foreground">And {rest} more: open the bell to see them all.</p>}
    </div>
  );
}

export function ProblemBell({ open, recent, onSeen, className }: {
  open: Problem[];
  recent: Problem[];
  onSeen: (id: number) => void;
  className?: string;
}) {
  const worst = open[0]?.severity;
  const Icon = open.length ? BellRing : Bell;
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon" className={cn("relative", className)}
          aria-label={open.length ? `Problems: ${open.length} open` : "Problems: none open"}>
          <Icon />
          {open.length > 0 && (
            <span className={cn("absolute -top-0.5 -right-0.5 grid min-w-5 place-items-center rounded-full px-1 text-[11px] font-bold text-white tabular-nums",
              worst === "critical" ? "bg-destructive" : "bg-amber-500")}>
              {open.length}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-[min(24rem,calc(100vw-2rem))] p-0">
        <div className="max-h-[70vh] overflow-y-auto">
          <h2 className="border-b px-4 py-3 font-semibold">Problems</h2>
          <ProblemList open={open} onSeen={onSeen} />
          {recent.length > 0 && (
            <>
              <h3 className="border-y bg-muted/50 px-4 py-2 text-xs font-semibold text-muted-foreground">Fixed in the last 7 days</h3>
              <ul className="divide-y">{recent.map((p) => <Row key={p.id} p={p} />)}</ul>
            </>
          )}
          <DesktopAlerts />
        </div>
      </PopoverContent>
    </Popover>
  );
}

/** Every open problem, worst first, for a page that lists them in full. */
export function ProblemList({ open, onSeen }: { open: Problem[]; onSeen: (id: number) => void }) {
  if (!open.length) {
    return (
      <p className="flex items-center gap-2 px-5 py-4 text-sm text-muted-foreground">
        <CircleCheck className="size-4 text-success-foreground" aria-hidden /> Nothing wrong right now.
      </p>
    );
  }
  return <ul className="divide-y">{open.map((p) => <Row key={p.id} p={p} onSeen={onSeen} />)}</ul>;
}

/** The worst open problem per clinic, for a dot beside its name. */
export function worstByClinic(open: Problem[]): Map<number, Problem["severity"]> {
  const out = new Map<number, Problem["severity"]>();
  for (const p of open) if (p.clinic_id !== null && !out.has(p.clinic_id)) out.set(p.clinic_id, p.severity);
  return out; // `open` comes worst first
}

export const SEVERITY_DOT = { critical: TONE.critical.dot, warning: TONE.warning.dot, info: TONE.info.dot };
export const SEVERITY_WORD = { critical: TONE.critical.word, warning: TONE.warning.word, info: TONE.info.word };

function Row({ p, onSeen }: { p: Problem; onSeen?: (id: number) => void }) {
  const tone = TONE[p.severity];
  const fixed = p.resolved_at !== null;
  return (
    <li className={cn("flex gap-3 px-4 py-3 text-sm", fixed && "text-muted-foreground")}>
      <span className={cn("mt-1.5 size-2 shrink-0 rounded-full", fixed ? "bg-success-foreground" : tone.dot)} aria-hidden />
      <div className="min-w-0 flex-1 space-y-1">
        <p className={cn("font-medium", !fixed && "text-foreground")}>
          <span className="sr-only">{fixed ? "Fixed" : tone.word}: </span>{p.title}
        </p>
        {!fixed && p.action && <p className="text-muted-foreground">{p.action}</p>}
        <p className="text-xs text-muted-foreground">
          {since(p.since)}{fixed && p.resolved_at ? `, fixed ${since(p.resolved_at).replace("since ", "")}` : ""}
        </p>
        {!fixed && (p.link || (onSeen && !p.seen && p.severity !== "critical")) && (
          <div className="flex gap-3 pt-0.5">
            {p.link && <Link href={p.link} className="text-xs font-medium text-primary hover:underline">Open</Link>}
            {onSeen && !p.seen && p.severity !== "critical" && (
              <button type="button" onClick={() => onSeen(p.id)} className="text-xs font-medium text-muted-foreground hover:text-foreground">
                Mark seen
              </button>
            )}
          </div>
        )}
      </div>
    </li>
  );
}

/** Desktop alerts need the browser's permission, asked for only on a click. */
function DesktopAlerts() {
  const [permission, setPermission] = useState(() =>
    typeof window !== "undefined" && "Notification" in window ? Notification.permission : "unsupported");
  if (permission === "unsupported" || permission === "granted") return null;
  return (
    <div className="border-t px-4 py-3 text-sm">
      {permission === "denied" ? (
        <p className="text-muted-foreground">Desktop alerts are blocked for this site in your browser&apos;s settings.</p>
      ) : (
        <Button size="sm" variant="outline" className="w-full"
          onClick={async () => setPermission(await Notification.requestPermission())}>
          <BellRing /> Alert me on this computer
        </Button>
      )}
    </div>
  );
}

/** While something is open: "(!)" or "(2)" in the tab title, a red dot on
 *  the tab's icon, and a desktop alert for each new problem. Problems
 *  already open when the page loads don't alert: the banner shows them. */
export function useProblemAlerts(open: Problem[] | undefined, heading: string) {
  const pathname = usePathname();
  const known = useRef<Set<number> | null>(null);
  const critical = open?.some((p) => p.severity === "critical") ?? false;
  const unseen = open ? bannered(open).length : 0;

  useEffect(() => {
    if (!open) return;
    if (known.current === null) {
      known.current = new Set(open.map((p) => p.id));
      return;
    }
    for (const p of open) {
      if (known.current.has(p.id)) continue;
      known.current.add(p.id);
      if (p.severity !== "info" && "Notification" in window && Notification.permission === "granted") {
        new Notification(`${heading}: ${p.severity === "critical" ? "urgent" : "needs attention"}`, { body: p.title, tag: `problem-${p.id}` });
      }
    }
  }, [open, heading]);

  // Page titles change on navigation, so the mark is re-applied then too.
  useEffect(() => {
    const clean = document.title.replace(/^\((!|\d+)\) /, "");
    document.title = critical ? `(!) ${clean}` : unseen ? `(${unseen}) ${clean}` : clean;
    const icon = document.querySelector<HTMLLinkElement>('link[rel~="icon"]');
    if (!icon) return;
    icon.dataset.normal ??= icon.href;
    icon.href = critical ? ALERT_ICON : icon.dataset.normal;
  }, [critical, unseen, pathname]);
}

const ALERT_ICON = `data:image/svg+xml,${encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><circle cx="16" cy="16" r="15" fill="#dc2626"/>' +
  '<rect x="14" y="7" width="4" height="12" rx="2" fill="#fff"/><circle cx="16" cy="24" r="2.4" fill="#fff"/></svg>',
)}`;
