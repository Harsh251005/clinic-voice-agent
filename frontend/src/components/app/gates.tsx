"use client";
// Full-page states shown instead of the dashboard: signed out, no access,
// errors. All on the same dark canvas and glass card as the sign-in page.
import type { ReactNode } from "react";
import Link from "next/link";
import { KeyRound, SearchX, WifiOff, type LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { AuthFrame } from "@/components/auth/auth-frame";
import { glassCard, glassEdge, glassMark, glassPrimary, glassQuiet } from "@/components/auth/glass";
import { api } from "@/lib/api/client";
import { PRODUCT_NAME } from "@/lib/product";
import { BrandMark } from "./brand";

export { glassPrimary, glassQuiet };

export function CenteredCard({ icon: Icon, title, description, children }: {
  icon: LucideIcon; title: string; description?: ReactNode; children?: ReactNode;
}) {
  return (
    <AuthFrame>
      <div className={glassCard}>
        <div aria-hidden className={glassEdge} />
        <span className="grid size-10 place-items-center rounded-xl bg-white/10 text-teal-200 ring-1 ring-white/10">
          <Icon className="size-5" aria-hidden />
        </span>
        <h1 className="mt-6 text-2xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-2 text-sm leading-relaxed text-white/60">{description}</p>}
        {children && <div className="mt-7 space-y-3">{children}</div>}
      </div>
    </AuthFrame>
  );
}

// The sign-in page lives with the other signed-out pages.
export { SignIn } from "@/components/auth/sign-in";

export async function signOut() {
  await api.POST("/api/auth/logout");
  // A full reload, not router.push: it guarantees no clinic data stays in
  // this tab's memory (the query cache) after signing out.
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.assign("/");
}

export function NoClinic({ email }: { email: string }) {
  return (
    <CenteredCard
      icon={KeyRound}
      title="No clinic yet"
      description={<>You&apos;re signed in as <b className="font-medium text-white">{email}</b>, but no clinic has added this address. Ask whoever manages {PRODUCT_NAME} for your clinic to add it.</>}
    >
      {/* Signing out is the only way forward here, so no confirmation step. */}
      <Button variant="outline" className={glassQuiet} onClick={signOut}>Sign out and use another account</Button>
    </CenteredCard>
  );
}

export function ClinicNotFound() {
  return (
    <CenteredCard icon={SearchX} title="Clinic not found" description="It doesn't exist, or your account can't open it.">
      <Button asChild className={glassPrimary}><Link href="/">Go to your clinics</Link></Button>
    </CenteredCard>
  );
}

/** Any address the dashboard doesn't have (src/app/not-found.tsx): never the framework's bare 404. */
export function PageNotFound() {
  return (
    <CenteredCard icon={SearchX} title="Page not found" description="This address doesn't lead anywhere. It may have been mistyped, or the page has moved.">
      <Button asChild className={glassPrimary}><Link href="/">Go to the dashboard</Link></Button>
    </CenteredCard>
  );
}

export function LoadError({ onRetry }: { onRetry: () => void }) {
  return (
    <CenteredCard icon={WifiOff} title="Can't connect" description={`We couldn't reach ${PRODUCT_NAME}. Check your internet connection, then try again.`}>
      <Button className={glassPrimary} onClick={onRetry}>Try again</Button>
    </CenteredCard>
  );
}

export function FullPageLoading() {
  return (
    <div className="grid min-h-screen md:grid-cols-[260px_1fr]" aria-busy>
      <div className="hidden space-y-4 border-r bg-sidebar p-5 md:block">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-full" />
      </div>
      <div className="space-y-4 p-6 md:p-10">
        <Skeleton className="h-9 w-64" />
        <Skeleton className="h-5 w-96 max-w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    </div>
  );
}

/** "/" while it finds out who you are: no dashboard skeleton, since the
 *  answer may well be the sign-in page. */
export function SplashLoading() {
  return (
    <div className="grid min-h-screen place-items-center bg-[#041416]" aria-busy aria-label="Loading">
      <BrandMark className={`size-12 rounded-2xl motion-safe:animate-pulse ${glassMark}`} />
    </div>
  );
}
