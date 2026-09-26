"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Plus, UserRound, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { useClinicChange } from "@/lib/queries";
import { Section } from "./section";

export function Team({ clinic }: { clinic: Schemas["Clinic"] }) {
  const [email, setEmail] = useState("");
  const path = { params: { path: { clinic_id: clinic.id } } };
  const members = useQuery({
    queryKey: ["members", clinic.id],
    queryFn: () => unwrap(api.GET("/api/clinics/{clinic_id}/members", path)),
  });
  const refresh = () => members.refetch();
  const add = useClinicChange(clinic.id, (body: Schemas["MemberIn"]) =>
    unwrap(api.POST("/api/clinics/{clinic_id}/members", { ...path, body })),
    (m) => `${m.email} can now open ${clinic.name}`);
  const remove = useClinicChange(clinic.id, (m: Schemas["Member"]) =>
    unwrap(api.DELETE("/api/clinics/{clinic_id}/members/{member_id}", { params: { path: { clinic_id: clinic.id, member_id: m.id } } })),
    (_r, m) => `${m.email} can no longer open ${clinic.name}`);

  return (
    <Section title="People with access"
      description="They sign in with the Google account for that address and see only this clinic. No invitation email is sent: send them the dashboard's address yourself.">
      <div className="space-y-5">
        {members.isPending ? <Skeleton className="h-16 w-full" /> : members.data?.length ? (
          <ul className="divide-y rounded-lg border">
            {members.data.map((m) => (
              <li key={m.id} className="flex items-center justify-between gap-3 px-4 py-2.5">
                <span className="flex min-w-0 items-center gap-2">
                  <UserRound className="size-4 shrink-0 text-muted-foreground" aria-hidden />
                  <span className="truncate">{m.email}</span>
                </span>
                <Button variant="ghost" size="sm" disabled={remove.isPending}
                  onClick={() => remove.mutate(m, { onSuccess: refresh })}>
                  <X /> Remove
                </Button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">Nobody yet. Admins can set the clinic up but can&apos;t see its patients.</p>
        )}
        <form className="flex flex-col gap-2 sm:flex-row" onSubmit={(e) => {
          e.preventDefault();
          add.mutate({ email }, { onSuccess: () => { setEmail(""); refresh(); } });
        }}>
          <Input type="email" required placeholder="reception@gmail.com" value={email} onChange={(e) => setEmail(e.target.value)}
            aria-label="Google account email" />
          <Button type="submit" disabled={add.isPending}><Plus /> Give access</Button>
        </form>
      </div>
    </Section>
  );
}
