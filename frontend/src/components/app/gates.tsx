"use client";
// Full-page states shown instead of the dashboard: signed out, no access, errors.
import type { ReactNode } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api/client";
import { PRODUCT_NAME } from "@/lib/product";
import { Brand } from "./brand";

export function CenteredCard({ title, description, children }: { title: string; description?: ReactNode; children?: ReactNode }) {
  return (
    <main className="grid min-h-screen place-items-center px-4 py-10">
      <div className="w-full max-w-sm">
        <Brand className="mb-6 justify-center" />
        <Card>
          <CardHeader>
            <CardTitle>{title}</CardTitle>
            {description && <CardDescription>{description}</CardDescription>}
          </CardHeader>
          {children && <CardContent className="space-y-4">{children}</CardContent>}
        </Card>
      </div>
    </main>
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
      title="No clinic yet"
      description={<>You&apos;re signed in as <b>{email}</b>, but no clinic has added this address. Ask the person who runs ClinicDesk for your clinic to add it.</>}
    >
      <Button variant="outline" className="w-full" onClick={signOut}>Sign out</Button>
    </CenteredCard>
  );
}

export function ClinicNotFound() {
  return (
    <CenteredCard title="Clinic not found" description="It doesn't exist, or your account can't open it.">
      <Button asChild variant="outline" className="w-full"><Link href="/">Go to your clinics</Link></Button>
    </CenteredCard>
  );
}

export function LoadError({ onRetry }: { onRetry: () => void }) {
  return (
    <CenteredCard title="Can't connect" description={`We couldn't reach ${PRODUCT_NAME}. Check your internet connection, then try again.`}>
      <Button className="w-full" onClick={onRetry}>Try again</Button>
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
