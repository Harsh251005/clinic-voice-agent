"use client";
// The sign-in page. Access is by invitation only: the admin adds a clinic and
// its staff's Google addresses. Nothing here may suggest signing up alone.
import { AlertCircle, ShieldCheck } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { PRODUCT_NAME } from "@/lib/product";
import { AuthFrame } from "./auth-frame";
import { GoogleButton } from "./google-button";
import { rise } from "./motion";

// Codes the API puts in ?signin= when Google sign-in goes wrong (api/dashboard/auth.py).
const PROBLEMS: Record<string, { title: string; body: string }> = {
  unverified: {
    title: "That account can't be used",
    body: "Google hasn't verified this account's email address. Verify it with Google, or use another account.",
  },
  failed: { title: "Sign-in didn't finish", body: "Something went wrong on the way back from Google. Please try again." },
};

export function SignIn({ problem }: { problem?: string | null }) {
  const shown = problem ? PROBLEMS[problem] : undefined;
  return (
    <AuthFrame>
      <div className={`${rise} [--tw-animation-delay:150ms]`}>
        <h1 className="text-2xl font-semibold tracking-tight">Sign in to {PRODUCT_NAME}</h1>
        <p className="mt-2 text-sm text-muted-foreground">Use the Google account your clinic added for you.</p>
      </div>

      {shown && (
        <Alert variant="destructive" className={`${rise} [--tw-animation-delay:200ms] mt-6`}>
          <AlertCircle />
          <AlertTitle>{shown.title}</AlertTitle>
          <AlertDescription>{shown.body}</AlertDescription>
        </Alert>
      )}

      <GoogleButton href="/api/auth/login" className={`${rise} [--tw-animation-delay:300ms] mt-8`} />

      <div className={`${rise} [--tw-animation-delay:420ms] mt-8 flex gap-3 rounded-lg border bg-card p-4 text-sm`}>
        <ShieldCheck className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
        <p className="text-muted-foreground">
          <span className="font-medium text-foreground">Access is by invitation.</span> Can&apos;t get in? Ask whoever
          manages {PRODUCT_NAME} for your clinic to add your Google address.
        </p>
      </div>
    </AuthFrame>
  );
}
