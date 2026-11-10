"use client";
// Who is an admin (Harsh, 2026-11-10): read-only on purpose. Admins are set in
// the server's .env (ADMIN_EMAILS), so nobody can make themselves admin from
// the dashboard or the database.
import { useQuery } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { api, unwrap } from "@/lib/api/client";

export function Admins() {
  const admins = useQuery({ queryKey: ["admin", "admins"], queryFn: () => unwrap(api.GET("/api/admin/admins")) });
  if (!admins.data) return null;
  const { emails, sign_in } = admins.data;
  return (
    <section aria-labelledby="h-admins" className="rounded-xl border bg-card px-5 py-4">
      <div className="flex items-center gap-2">
        <ShieldCheck className="size-4 text-muted-foreground" aria-hidden />
        <h2 id="h-admins" className="font-semibold">Admins</h2>
      </div>
      <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
        Admins see and change every clinic, including patients&apos; call transcripts. They are set only in the
        server&apos;s <code>.env</code> (<code>ADMIN_EMAILS</code>, comma-separated; restart the API after a change),
        so nobody can add themselves here.
      </p>
      {sign_in === "off" ? (
        <p className="mt-3 text-sm">Sign-in is off on this server: everyone who opens it is an admin.</p>
      ) : emails.length ? (
        <ul className="mt-3 flex flex-wrap gap-2">
          {emails.map((e) => <li key={e} className="rounded-full bg-muted px-3 py-1 text-sm">{e}</li>)}
        </ul>
      ) : (
        <p className="mt-3 text-sm text-destructive">No admins are set.</p>
      )}
    </section>
  );
}
