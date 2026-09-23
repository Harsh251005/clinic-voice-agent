"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Brand } from "@/components/app/brand";
import { FullPageLoading, LoadError, SignIn } from "@/components/app/gates";
import { PageHeader } from "@/components/app/page-header";
import { Field } from "@/components/setup/field";
import { Section } from "@/components/setup/section";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { keys, useMe } from "@/lib/queries";

export default function NewClinicPage() {
  const me = useMe();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<Schemas["NewClinic"]>({ name: "", address: "", phone: "" });
  const create = useMutation({
    mutationFn: (body: Schemas["NewClinic"]) => unwrap(api.POST("/api/clinics", { body })),
    onSuccess: async (c) => {
      toast.success(`${c.name} created. Add its doctors next.`);
      await queryClient.invalidateQueries({ queryKey: keys.me });
      router.push(`/clinics/${c.id}/setup?tab=doctors`);
    },
    onError: (err) => toast.error(err.message),
  });

  if (me.isPending) return <FullPageLoading />;
  if (me.isError) return <LoadError onRetry={() => me.refetch()} />;
  if (me.data === null) return <SignIn />;

  const back = me.data.clinics[0] ? `/clinics/${me.data.clinics[0].id}/today` : null;
  return (
    <main className="mx-auto w-full max-w-2xl px-4 py-8 md:py-12">
      <div className="mb-8 flex items-center justify-between">
        <Brand />
        {back && <Button variant="ghost" asChild><Link href={back}><ArrowLeft /> Back</Link></Button>}
      </div>
      {!me.data.is_admin ? (
        <PageHeader title="Only admins can add clinics" description="Ask the person who runs this dashboard." />
      ) : (
        <>
          <PageHeader title="Set up a new clinic" description="Start with the basics. Doctors, hours and answers come next." />
          <form onSubmit={(e) => { e.preventDefault(); create.mutate({ ...form, name: form.name.trim() }); }}>
            <Section title="Clinic details">
              <div className="space-y-4">
                <Field id="name" label="Clinic name">
                  <Input id="name" required maxLength={200} placeholder="Sharma Family Clinic" value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })} />
                </Field>
                <Field id="address" label="Address">
                  <Textarea id="address" rows={2} maxLength={500} placeholder="Shop 4, Sunrise Apartments, Borivali East, Mumbai"
                    value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
                </Field>
                <Field id="phone" label="Phone">
                  <Input id="phone" maxLength={20} inputMode="tel" placeholder="022 1234 5678" value={form.phone}
                    onChange={(e) => setForm({ ...form, phone: e.target.value })} />
                </Field>
                <div className="flex justify-end">
                  <Button type="submit" disabled={create.isPending}>{create.isPending ? "Creating…" : "Create clinic"}</Button>
                </div>
              </div>
            </Section>
          </form>
        </>
      )}
    </main>
  );
}
