// What ClinicDesk does, in four tiles, on the sign-in page. Each tile says one
// thing, once, and only what is built (check the code before adding a claim).
// A soft light passes over one tile after another, forever: the page's quiet
// motion (motion-safe; still for viewers who ask for less).
import type { CSSProperties } from "react";
import { CalendarCheck, ClipboardList, FileText, MessageCircleQuestionMark, type LucideIcon } from "lucide-react";
import { PRODUCT_NAME } from "@/lib/product";

type Tile = { icon: LucideIcon; title: string; body: string };

const TILES: Tile[] = [
  {
    icon: CalendarCheck,
    title: "Books, moves, cancels",
    body: "Offers the doctor's free times and reads the details back. It books only after the patient says yes, and never double-books.",
  },
  {
    icon: MessageCircleQuestionMark,
    title: "Answers questions",
    body: "Your doctors, opening hours, holidays and leave, plus the FAQ you write.",
  },
  {
    icon: ClipboardList,
    title: "Keeps your diary",
    body: "New bookings show up in today's list, and staff mark each patient arrived, done or no-show.",
  },
  {
    icon: FileText,
    title: "Every call on record",
    body: "Each call's outcome, plus its transcript for 30 days. No audio is kept.",
  },
];

// One full pass over the tiles (animate-tile-glow in globals.css). Negative
// delays: every tile is mid-cycle from the first frame, lit in reading order.
const PASS_S = 10;
const delay = (i: number) => `-${(PASS_S / TILES.length) * ((TILES.length - i) % TILES.length)}s`;

export function Offering({ className }: { className?: string }) {
  return (
    <section aria-label={`What ${PRODUCT_NAME} does`} className={className}>
      <ul className="grid gap-3 sm:grid-cols-2">
        {TILES.map(({ icon: Icon, title, body }, i) => (
          <li
            key={title}
            className="rounded-xl bg-white/[0.03] p-4 ring-1 ring-white/10 backdrop-blur-xl motion-safe:animate-tile-glow"
            style={{ animationDelay: delay(i) } as CSSProperties}
          >
            <Icon aria-hidden className="size-5 text-teal-300" />
            <h2 className="mt-3 font-medium text-white">{title}</h2>
            <p className="mt-1 text-sm leading-relaxed text-white/55">{body}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
