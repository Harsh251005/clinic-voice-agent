"use client";
import { useState } from "react";
import { Check, Copy, ExternalLink, TriangleAlert } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { useClinicChange } from "@/lib/queries";
import { Field } from "./field";
import { Section } from "./section";

export function CallLink({ clinic }: { clinic: Schemas["Clinic"] }) {
  const [copied, setCopied] = useState(false);
  const [slug, setSlug] = useState(clinic.slug);
  const rename = useClinicChange(clinic.id, (next: string) =>
    unwrap(api.PUT("/api/clinics/{clinic_id}/slug", { params: { path: { clinic_id: clinic.id } }, body: { slug: next } })),
    "Web address saved. The old link no longer works.",
  );

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(clinic.call_link);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("Couldn't copy. Select the link and copy it by hand.");
    }
  };

  return (
    <div className="space-y-6">
      <Section title="Share this link"
        description="Patients open it on their phone or computer and talk to the receptionist in the browser. Put it on your website, WhatsApp or Google listing.">
        <div className="flex flex-col gap-2 sm:flex-row">
          <Input readOnly value={clinic.call_link} className="font-mono text-sm" onFocus={(e) => e.target.select()} aria-label="Receptionist link" />
          <div className="flex gap-2">
            <Button onClick={copy} className="flex-1 sm:flex-none">{copied ? <Check /> : <Copy />} {copied ? "Copied" : "Copy"}</Button>
            <Button variant="outline" asChild className="flex-1 sm:flex-none">
              <a href={clinic.call_link} target="_blank" rel="noreferrer"><ExternalLink /> Open</a>
            </Button>
          </div>
        </div>
      </Section>
      <Section title="Web address">
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); rename.mutate(slug.trim().toLowerCase()); }}>
          <Field id="slug" label="Web address" hint="The end of your link. Small letters, numbers and dashes, e.g. sharma-skin.">
            <Input id="slug" value={slug} onChange={(e) => setSlug(e.target.value)} className="font-mono" />
          </Field>
          <p className="flex items-start gap-2 text-sm text-warning-foreground">
            <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
            Changing it stops the old link from working. Update it everywhere you shared it.
          </p>
          <div className="flex justify-end">
            <Button type="submit" disabled={slug === clinic.slug || rename.isPending}>Save web address</Button>
          </div>
        </form>
      </Section>
    </div>
  );
}
