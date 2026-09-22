"use client";
// The signed-in frame: sidebar (clinic switcher, pages, account) around a page.
import { useEffect, type ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { CalendarDays, LogOut, Plus, Settings2, TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { useMe } from "@/lib/queries";
import { rememberClinic } from "@/lib/last-clinic";
import { Brand } from "./brand";
import { ClinicNotFound, FullPageLoading, LoadError, NoClinic, SignIn, signOut } from "./gates";

const PAGES = [
  { segment: "appointments", label: "Appointments", icon: CalendarDays },
  { segment: "setup", label: "Clinic setup", icon: Settings2 },
] as const;

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
  const current = pathname.split("/")[3] ?? "appointments";

  return (
    <div className="min-h-screen md:grid md:grid-cols-[260px_1fr]">
      <aside className="flex flex-col gap-3 border-b bg-sidebar p-4 md:sticky md:top-0 md:h-screen md:gap-5 md:border-r md:border-b-0 md:p-5">
        <div className="flex items-center justify-between">
          <Brand />
          {/* On a phone the sidebar is a compact header: actions become icons here. */}
          <div className="flex items-center md:hidden">
            {is_admin && (
              <Button variant="ghost" size="icon" asChild aria-label="New clinic" title="New clinic">
                <Link href="/new-clinic"><Plus /></Link>
              </Button>
            )}
            {login !== "off" && (
              <Button variant="ghost" size="icon" onClick={signOut} aria-label="Sign out" title="Sign out">
                <LogOut />
              </Button>
            )}
          </div>
        </div>
        <div className="space-y-1.5">
          <p className="hidden text-xs font-medium text-muted-foreground md:block">Clinic</p>
          <Select
            value={String(clinicId)}
            onValueChange={(id) => router.push(`/clinics/${id}/${current}`)}
          >
            <SelectTrigger className="w-full bg-background" aria-label="Clinic">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {clinics.map((c) => (
                <SelectItem key={c.id} value={String(c.id)}>{c.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <nav className="flex gap-1 md:flex-col" aria-label="Pages">
          {PAGES.map(({ segment, label, icon: Icon }) => (
            <Link
              key={segment}
              href={`/clinics/${clinicId}/${segment}`}
              aria-current={current === segment ? "page" : undefined}
              className={cn(
                "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                current === segment && "bg-sidebar-accent text-sidebar-accent-foreground",
              )}
            >
              <Icon className="size-4" aria-hidden /> {label}
            </Link>
          ))}
        </nav>

        {is_admin && (
          <Button variant="outline" asChild className="hidden justify-start md:flex">
            <Link href="/new-clinic"><Plus /> New clinic</Link>
          </Button>
        )}

        <div className="space-y-3 md:mt-auto">
          <Separator className="hidden md:block" />
          {login === "off" ? (
            <p className="flex gap-2 text-xs text-warning-foreground">
              <TriangleAlert className="size-4 shrink-0" aria-hidden />
              Sign-in is off (DASHBOARD_LOGIN=off). Local development only.
            </p>
          ) : (
            <div className="hidden items-center justify-between gap-2 md:flex">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium" title={email}>{email}</p>
                <p className="text-xs text-muted-foreground">{is_admin ? "Admin" : "Clinic staff"}</p>
              </div>
              <Button variant="ghost" size="icon" onClick={signOut} aria-label="Sign out" title="Sign out">
                <LogOut />
              </Button>
            </div>
          )}
        </div>
      </aside>
      <main className="mx-auto w-full max-w-6xl px-4 py-8 md:px-10 md:py-10">{children}</main>
    </div>
  );
}
