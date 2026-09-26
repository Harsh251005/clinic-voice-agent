"use client";
// The operator's frame: slate ink with an amber mark, deliberately unlike a
// clinic's teal shell. Sidebar on computers and tablets; top bar plus bottom
// tabs on phones. Admins only.
import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, Building2, LayoutDashboard, LogOut, PhoneCall, TriangleAlert, FlaskConical } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useMe } from "@/lib/queries";
import { PRODUCT_NAME } from "@/lib/product";
import { BrandMark } from "@/components/app/brand";
import { CenteredCard, FullPageLoading, LoadError, SignIn, signOut } from "@/components/app/gates";

const PAGES = [
  { href: "/admin", label: "Health", icon: Activity },
  { href: "/admin/calls", label: "Calls", icon: PhoneCall },
  { href: "/admin/errors", label: "Errors", icon: TriangleAlert },
  { href: "/admin/clinics", label: "Clinics", icon: Building2 },
] as const;

function isCurrent(pathname: string, href: string) {
  return href === "/admin" ? pathname === "/admin" : pathname.startsWith(href);
}

export function AdminShell({ children }: { children: ReactNode }) {
  const me = useMe();
  const pathname = usePathname();

  if (me.isPending) return <FullPageLoading />;
  if (me.isError) return <LoadError onRetry={() => me.refetch()} />;
  if (me.data === null) return <SignIn />;
  if (!me.data.is_admin) {
    return (
      <CenteredCard title="Admins only" description="This part of the dashboard is for the people who run the service.">
        <Button asChild variant="outline" className="w-full"><Link href="/">Go to your clinic</Link></Button>
      </CenteredCard>
    );
  }
  const { email, login, clinics } = me.data;
  const hasClinics = clinics.length > 0;

  return (
    <div className="min-h-screen md:grid md:grid-cols-[232px_1fr]">
      <aside className="hidden flex-col gap-6 bg-ops p-4 text-ops-foreground md:sticky md:top-0 md:flex md:h-screen">
        <div className="flex items-center gap-2.5 px-2 pt-1">
          <BrandMark className="bg-ops-primary text-ops" />
          <div className="leading-tight">
            <p className="text-base font-semibold tracking-tight text-ops-accent-foreground">{PRODUCT_NAME}</p>
            <p className="text-[11px] font-semibold tracking-wider text-ops-primary uppercase">Operator</p>
          </div>
        </div>

        <nav className="flex flex-col gap-0.5" aria-label="Admin pages">
          {PAGES.map(({ href, label, icon: Icon }) => {
            const on = isCurrent(pathname, href);
            return (
              <Link key={href} href={href} aria-current={on ? "page" : undefined}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-[15px] font-medium transition-colors hover:bg-ops-accent/70 hover:text-ops-accent-foreground",
                  on && "bg-ops-accent text-ops-accent-foreground",
                )}>
                <Icon className={cn("size-[18px]", on && "text-ops-primary")} aria-hidden /> {label}
              </Link>
            );
          })}
        </nav>

        <div className="mt-auto space-y-4">
          {hasClinics && (
            <Link href="/" className="mx-1 flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:text-ops-accent-foreground">
              <LayoutDashboard className="size-4" aria-hidden /> Clinic dashboard
            </Link>
          )}
          {login === "off" ? (
            <p className="mx-2 flex items-center gap-2 rounded-md bg-warning/15 px-2.5 py-2 text-xs text-warning">
              <FlaskConical className="size-4 shrink-0" aria-hidden /> Test mode: sign-in is off
            </p>
          ) : (
            <div className="flex items-center justify-between gap-2 border-t border-ops-border px-2 pt-4">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-ops-accent-foreground" title={email}>{email}</p>
                <p className="text-xs">Admin</p>
              </div>
              <Button variant="ghost" size="icon" onClick={signOut} aria-label="Sign out" title="Sign out"
                className="text-ops-foreground hover:bg-ops-accent hover:text-ops-accent-foreground">
                <LogOut />
              </Button>
            </div>
          )}
        </div>
      </aside>

      <header className="sticky top-0 z-20 flex items-center gap-3 bg-ops px-4 py-3 text-ops-foreground md:hidden">
        <BrandMark className="size-7 bg-ops-primary text-ops" />
        <p className="flex-1 font-semibold text-ops-accent-foreground">
          {PRODUCT_NAME} <span className="text-xs font-semibold tracking-wider text-ops-primary uppercase">Operator</span>
        </p>
        {hasClinics && (
          <Button variant="ghost" size="icon" asChild aria-label="Clinic dashboard" title="Clinic dashboard"
            className="text-ops-foreground hover:bg-ops-accent hover:text-ops-accent-foreground">
            <Link href="/"><LayoutDashboard /></Link>
          </Button>
        )}
        {login !== "off" && (
          <Button variant="ghost" size="icon" onClick={signOut} aria-label="Sign out" title="Sign out"
            className="text-ops-foreground hover:bg-ops-accent hover:text-ops-accent-foreground">
            <LogOut />
          </Button>
        )}
      </header>
      <nav aria-label="Admin pages"
        className="fixed inset-x-0 bottom-0 z-20 grid grid-cols-4 border-t bg-card/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden">
        {PAGES.map(({ href, label, icon: Icon }) => {
          const on = isCurrent(pathname, href);
          return (
            <Link key={href} href={href} aria-current={on ? "page" : undefined}
              className={cn("flex flex-col items-center gap-1 py-2.5 text-xs font-medium text-muted-foreground", on && "text-foreground")}>
              <Icon className={cn("size-5", on && "text-amber-600 dark:text-ops-primary")} aria-hidden /> {label}
            </Link>
          );
        })}
      </nav>

      <main className="mx-auto w-full max-w-6xl px-4 pt-6 pb-28 md:px-10 md:py-10">{children}</main>
    </div>
  );
}
