"use client";
// The sign-in card. Access is by invitation only: the admin adds a clinic and
// its staff's Google addresses. Nothing here may suggest signing up alone.
import { AlertCircle, ShieldCheck } from "lucide-react";
import { BrandMark } from "@/components/app/brand";
import { PRODUCT_NAME } from "@/lib/product";
import { AuthFrame } from "./auth-frame";
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
    <AuthFrame>
      {/* Fixed light colours, not theme tokens: this card looks the same for everyone. */}
      <div className="relative rounded-2xl bg-white p-8 text-slate-900 shadow-[0_40px_100px_-30px_rgba(0,0,0,0.8)] ring-1 ring-white/20">
        <div aria-hidden className="absolute inset-x-10 -top-px h-px bg-gradient-to-r from-transparent via-teal-400 to-transparent" />
        <BrandMark className="size-10 rounded-xl" />
        <h1 className="mt-6 text-2xl font-semibold tracking-tight">Sign in</h1>
        <p className="mt-1.5 text-sm text-slate-500">Use the Google account your clinic added for you.</p>

        {shown && (
          <div role="alert" className="mt-6 flex gap-3 rounded-lg bg-red-50 p-3.5 text-sm ring-1 ring-red-200">
            <AlertCircle className="mt-0.5 size-4 shrink-0 text-red-600" aria-hidden />
            <div>
              <p className="font-medium text-red-800">{shown.title}</p>
              <p className="mt-0.5 text-red-700">{shown.body}</p>
            </div>
          </div>
        )}

        <GoogleButton href="/api/auth/login" className="mt-7" />

        <div className="my-7 h-px bg-slate-100" />

        <div className="flex gap-3 text-sm">
          <ShieldCheck className="mt-0.5 size-4 shrink-0 text-teal-700" aria-hidden />
          <p className="text-slate-500">
            <span className="font-medium text-slate-800">Access is by invitation.</span> Can&apos;t get in? Ask whoever
            manages {PRODUCT_NAME} for your clinic to add your Google address.
          </p>
        </div>
      </div>
    </AuthFrame>
  );
}
