"use client";
// The sign-in card. Access is by invitation only: the admin adds a clinic and
// its staff's Google addresses. Nothing here may suggest signing up alone.
import { AlertCircle, ShieldCheck } from "lucide-react";
import { PRODUCT_NAME } from "@/lib/product";
import { AuthFrame } from "./auth-frame";
import { glassCard, glassEdge } from "./glass";
import { GoogleButton } from "./google-button";

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
    <AuthFrame pitch>
      {/* Frosted glass like the example call beside it: one page, not a box on top. */}
      <div className={glassCard}>
        <div aria-hidden className={glassEdge} />
        <h1 className="text-2xl font-semibold tracking-tight">Sign in</h1>
        <p className="mt-1.5 text-sm text-white/55">Use the Google account your clinic added for you.</p>

        {shown && (
          <div role="alert" className="mt-6 flex gap-3 rounded-lg bg-red-500/10 p-3.5 text-sm ring-1 ring-red-400/30">
            <AlertCircle className="mt-0.5 size-4 shrink-0 text-red-300" aria-hidden />
            <div>
              <p className="font-medium text-red-100">{shown.title}</p>
              <p className="mt-0.5 text-red-200/80">{shown.body}</p>
            </div>
          </div>
        )}

        <GoogleButton href="/api/auth/login" className="mt-7" />

        <div className="my-7 h-px bg-white/10" />

        <div className="flex gap-3 text-sm">
          <ShieldCheck className="mt-0.5 size-4 shrink-0 text-teal-300" aria-hidden />
          <p className="text-white/55">
            <span className="font-medium text-white/90">Access is by invitation.</span> Can&apos;t get in? Ask whoever
            manages {PRODUCT_NAME} for your clinic to add your Google address.
          </p>
        </div>
      </div>
    </AuthFrame>
  );
}
