"use client";
// Full-page states shown instead of the dashboard: signed out, no access, errors.
import type { ReactNode } from "react";
import Link from "next/link";
import { AlertCircle, LogIn } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api/client";
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

const SIGN_IN_PROBLEMS: Record<string, string> = {
  unverified: "Google hasn't verified that account's email address, so it can't be used here.",
  failed: "Sign-in didn't complete. Please try again.",
};

export function SignIn({ problem }: { problem?: string | null }) {
  return (
    <CenteredCard title="Sign in" description="Use the Google account your clinic added to the dashboard.">
      {problem && SIGN_IN_PROBLEMS[problem] && (
        <Alert variant="destructive">
          <AlertCircle />
          <AlertDescription>{SIGN_IN_PROBLEMS[problem]}</AlertDescription>
        </Alert>
      )}
      <Button asChild className="w-full" size="lg">
        {/* A full navigation, not fetch: the API sends the browser on to Google. */}
        <a href="/api/auth/login">
          <LogIn /> Sign in with Google
        </a>
      </Button>
    </CenteredCard>
  );
}

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
      description={<>You&apos;re signed in as <b>{email}</b>, but no clinic has added this address. Ask the person who set up your clinic to add it on the Team tab.</>}
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
    <CenteredCard title="Can't reach the dashboard" description="The server didn't answer. Check that it's running, then try again.">
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
