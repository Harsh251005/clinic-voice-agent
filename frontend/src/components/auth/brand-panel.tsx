// The left half of the signed-out pages: what ClinicDesk is, in claims that
// are all built today. Add a claim here only in the change that builds it.
import { CalendarCheck, FileText, LayoutDashboard, type LucideIcon } from "lucide-react";
import { Brand } from "@/components/app/brand";
import { rise } from "./motion";
import { TodayPreview } from "./today-preview";

// Each point enters after the one above it.
const POINT_DELAYS = ["[--tw-animation-delay:300ms]", "[--tw-animation-delay:420ms]", "[--tw-animation-delay:540ms]"];

const POINTS: { icon: LucideIcon; title: string; body: string }[] = [
  { icon: CalendarCheck, title: "Books by voice, in Hindi", body: "Patients book, move or cancel their visit by talking to the receptionist." },
  { icon: FileText, title: "Every call written down", body: "Each call is kept with its transcript, so you see what was said." },
  { icon: LayoutDashboard, title: "Your day in one place", body: "Today's patients, the diary and anything that needs you." },
];

export function BrandPanel() {
  return (
    <aside className="relative hidden overflow-hidden bg-sidebar text-sidebar-foreground lg:flex lg:flex-col">
      {/* A soft glow and a faint dot grid: texture, not decoration to read. */}
      <div aria-hidden className="pointer-events-none absolute -top-40 -left-32 size-[520px] rounded-full bg-sidebar-primary/15 blur-3xl motion-safe:animate-drift" />
      <div aria-hidden className="pointer-events-none absolute -right-40 -bottom-48 size-[480px] rounded-full bg-sidebar-primary/10 blur-3xl motion-safe:animate-drift motion-safe:direction-alternate-reverse" />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.07] [background-image:radial-gradient(currentColor_1px,transparent_1px)] [background-size:22px_22px]"
      />

      <div className="relative flex flex-1 flex-col px-12 py-10 xl:px-16">
        <Brand className={`text-sidebar-accent-foreground ${rise}`} />

        <div className="my-auto max-w-md py-12">
          <p className={`${rise} [--tw-animation-delay:100ms] text-3xl leading-tight font-semibold tracking-tight text-balance text-sidebar-accent-foreground xl:text-4xl`}>
            Your clinic&apos;s front desk, answering in Hindi.
          </p>
          <p className={`${rise} [--tw-animation-delay:200ms] mt-4 text-base leading-relaxed text-pretty`}>
            A voice receptionist that books appointments, and a dashboard for the staff who run the day.
          </p>

          <ul className="mt-10 space-y-5">
            {POINTS.map(({ icon: Icon, title, body }, i) => (
              <li key={title} className={`${rise} ${POINT_DELAYS[i]} flex gap-4`}>
                <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-sidebar-accent text-sidebar-primary ring-1 ring-sidebar-border">
                  <Icon className="size-[18px]" aria-hidden />
                </span>
                <div>
                  <p className="font-medium text-sidebar-accent-foreground">{title}</p>
                  <p className="mt-0.5 text-sm leading-relaxed">{body}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <TodayPreview />
      </div>
    </aside>
  );
}
