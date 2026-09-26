"use client";
// The signed-in frame: a teal-ink sidebar (clinic, pages, account) on
// computers and tablets; a top bar plus a bottom tab bar on phones.
import { useEffect, type ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { CalendarDays, Gauge, House, LogOut, Settings2, FlaskConical, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { Schemas } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { useMe } from "@/lib/queries";
import { rememberClinic } from "@/lib/last-clinic";
import { PRODUCT_NAME } from "@/lib/product";
import { BrandMark } from "./brand";
import { ClinicNotFound, FullPageLoading, LoadError, NoClinic, SignIn, signOut } from "./gates";

// `staff`: shows patients, so only the clinic's own members see it. An admin
// who isn't a member sets the clinic up but never sees its patients.
const PAGES = [
  { segment: "today", label: "Today", icon: House, staff: true },
  { segment: "appointments", label: "Appointments", icon: CalendarDays, staff: true },
  { segment: "setup", label: "Clinic settings", short: "Settings", icon: Settings2, staff: false },
] as const;

/** Where a clinic opens: Today for its staff, settings for an admin. */
export function clinicHome(clinic: Schemas["ClinicSummary"]) {
  return `/clinics/${clinic.id}/${clinic.staff ? "today" : "setup"}`;
}

export function AppShell({ clinicId, children }: { clinicId: number; children: ReactNode }) {
  const me = useMe();
  const pathname = usePathname();
  const router = useRouter();
  const allowed = me.data?.clinics.some((c) => c.id === clinicId);
  useEffect(() => {
    if (allowed) rememberClinic(clinicId);
  }, [allowed, clinicId]);

  if (me.isPending) return <FullPageLoading />;
  if (me.isError) return <LoadError onRetry={() => me.refetch()} />;
  if (me.data === null) return <SignIn />;
  if (!me.data.is_admin && me.data.clinics.length === 0) return <NoClinic email={me.data.email} />;
  if (!allowed) return <ClinicNotFound />;

  const { clinics, email, is_admin, login } = me.data;
  const current = pathname.split("/")[3] ?? "today";
  const clinic = clinics.find((c) => c.id === clinicId);
  const clinicName = clinic?.name ?? "";
  const staff = clinic?.staff ?? false;
  const pages = PAGES.filter((p) => staff || !p.staff);
  const blocked = !staff && PAGES.some((p) => p.segment === current && p.staff);

  // Staff of one clinic just see its name; a switcher only when there's a choice.
  const clinicPicker = clinics.length > 1 ? (
    <Select value={String(clinicId)} onValueChange={(id) => {
      const next = clinics.find((c) => c.id === Number(id));
      if (!next) return;
      const page = PAGES.find((p) => p.segment === current);
      router.push(page && (next.staff || !page.staff) ? `/clinics/${id}/${current}` : clinicHome(next));
    }}>
      <SelectTrigger aria-label="Clinic"
        className="h-auto w-full border-sidebar-border bg-sidebar-accent/60 py-2 text-left font-medium text-sidebar-accent-foreground [&_svg]:text-sidebar-foreground">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {clinics.map((c) => <SelectItem key={c.id} value={String(c.id)}>{c.name}</SelectItem>)}
      </SelectContent>
    </Select>
  ) : (
    <p className="truncate font-medium text-sidebar-accent-foreground" title={clinicName}>{clinicName}</p>
  );

  return (
    <div className="min-h-screen md:grid md:grid-cols-[248px_1fr]">
      {/* Computers and tablets: the sidebar. */}
      <aside className="hidden flex-col gap-6 bg-sidebar p-4 text-sidebar-foreground md:sticky md:top-0 md:flex md:h-screen">
        <div className="flex items-center gap-2.5 px-2 pt-1">
          <BrandMark className="bg-sidebar-primary text-sidebar-primary-foreground" />
          <span className="text-base font-semibold tracking-tight text-sidebar-accent-foreground">{PRODUCT_NAME}</span>
        </div>

        <div className="space-y-1.5 px-2">
          <p className="text-[11px] font-semibold tracking-wider uppercase opacity-70">Clinic</p>
          {clinicPicker}
        </div>

        <nav className="flex flex-col gap-0.5" aria-label="Pages">
          {pages.map(({ segment, label, icon: Icon }) => (
            <Link
              key={segment}
              href={`/clinics/${clinicId}/${segment}`}
              aria-current={current === segment ? "page" : undefined}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-[15px] font-medium transition-colors hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground",
                current === segment && "bg-sidebar-accent text-sidebar-accent-foreground",
              )}
            >
              <Icon className={cn("size-[18px]", current === segment && "text-sidebar-primary")} aria-hidden /> {label}
            </Link>
          ))}
        </nav>

        <div className="mt-auto space-y-4">
          {is_admin && (
            <div className="space-y-1.5 px-2">
              <p className="text-[11px] font-semibold tracking-wider uppercase opacity-70">Admin</p>
              <Link href="/admin"
                className="-mx-1 flex items-center gap-2 rounded-md px-1 py-1.5 text-sm hover:text-sidebar-accent-foreground">
                <Gauge className="size-4" aria-hidden /> Admin panel
              </Link>
            </div>
          )}
          {login === "off" ? (
            <p className="mx-2 flex items-center gap-2 rounded-md bg-warning/15 px-2.5 py-2 text-xs text-warning">
              <FlaskConical className="size-4 shrink-0" aria-hidden /> Test mode: sign-in is off
            </p>
          ) : (
            <div className="flex items-center justify-between gap-2 border-t border-sidebar-border px-2 pt-4">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-sidebar-accent-foreground" title={email}>{email}</p>
                <p className="text-xs">{is_admin ? "Admin" : "Clinic staff"}</p>
              </div>
              <Button variant="ghost" size="icon" onClick={signOut} aria-label="Sign out" title="Sign out"
                className="text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground">
                <LogOut />
              </Button>
            </div>
          )}
        </div>
      </aside>

      {/* Phones: a top bar with the clinic, and tabs at the bottom. */}
      <header className="sticky top-0 z-20 flex items-center gap-3 bg-sidebar px-4 py-3 text-sidebar-foreground md:hidden">
        <BrandMark className="size-7 bg-sidebar-primary text-sidebar-primary-foreground" />
        <div className="min-w-0 flex-1">{clinicPicker}</div>
        {is_admin && (
          <Button variant="ghost" size="icon" asChild aria-label="Admin panel" title="Admin panel"
            className="text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground">
            <Link href="/admin"><Gauge /></Link>
          </Button>
        )}
        {login !== "off" && (
          <Button variant="ghost" size="icon" onClick={signOut} aria-label="Sign out" title="Sign out"
            className="text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground">
            <LogOut />
          </Button>
        )}
      </header>
      <nav aria-label="Pages"
        style={{ gridTemplateColumns: `repeat(${pages.length}, minmax(0, 1fr))` }}
        className="fixed inset-x-0 bottom-0 z-20 grid border-t bg-card/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden">
        {pages.map(({ segment, label, icon: Icon, ...rest }) => (
          <Link
            key={segment}
            href={`/clinics/${clinicId}/${segment}`}
            aria-current={current === segment ? "page" : undefined}
            className={cn(
              "flex flex-col items-center gap-1 py-2.5 text-xs font-medium text-muted-foreground",
              current === segment && "text-primary",
            )}
          >
            <Icon className="size-5" aria-hidden /> {"short" in rest ? rest.short : label}
          </Link>
        ))}
      </nav>

      <main className="mx-auto w-full max-w-6xl px-4 pt-6 pb-28 md:px-10 md:py-10">
        {login === "off" && (
          <p className="mb-4 flex items-center gap-2 text-xs text-warning-foreground md:hidden">
            <FlaskConical className="size-4" aria-hidden /> Test mode: sign-in is off
          </p>
        )}
        {blocked ? <StaffOnly clinicId={clinicId} /> : children}
      </main>
    </div>
  );
}

/** An admin on a page with patients on it: say why it's closed, and where to go. */
function StaffOnly({ clinicId }: { clinicId: number }) {
  return (
    <div className="mx-auto max-w-md space-y-4 py-16 text-center">
      <span className="mx-auto grid size-12 place-items-center rounded-xl bg-muted text-muted-foreground">
        <ShieldCheck className="size-6" aria-hidden />
      </span>
      <h1 className="text-xl font-semibold tracking-tight">For the clinic&apos;s staff only</h1>
      <p className="text-muted-foreground">
        This page shows patients&apos; names, numbers and visits. As an admin you can set the clinic up,
        but only people on its team can see its patients.
      </p>
      <Button asChild><Link href={`/clinics/${clinicId}/setup`}>Open clinic settings</Link></Button>
    </div>
  );
}
