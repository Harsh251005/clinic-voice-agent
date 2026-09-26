"use client";
import { Suspense } from "react";
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation";
import { AlertCircle } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/app/page-header";
import { CallLink } from "@/components/setup/call-link";
import { ClinicDetails } from "@/components/setup/clinic-details";
import { Doctors } from "@/components/setup/doctors";
import { Faq } from "@/components/setup/faq";
import { Hours } from "@/components/setup/hours";
import { TimeOff } from "@/components/setup/time-off";
import { useClinic } from "@/lib/queries";

const TABS = [
  { id: "clinic", label: "Clinic details", Panel: ClinicDetails },
  { id: "link", label: "Receptionist link", Panel: CallLink },
  { id: "doctors", label: "Doctors", Panel: Doctors },
  { id: "hours", label: "Weekly hours", Panel: Hours },
  { id: "time-off", label: "Leave & holidays", Panel: TimeOff },
  { id: "faq", label: "Common questions", Panel: Faq },
] as const;

function Setup() {
  const clinicId = Number(useParams<{ clinicId: string }>().clinicId);
  const clinic = useClinic(clinicId);
  const search = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const tabs = TABS; // the team is managed in the admin panel (Clinics)
  const tab = tabs.some((t) => t.id === search.get("tab")) ? search.get("tab")! : "clinic";

  return (
    <>
      <PageHeader title={clinic.data?.name ?? "Clinic settings"}
        description="Everything the receptionist says about this clinic comes from these details." />
      {clinic.isError ? (
        <Alert variant="destructive"><AlertCircle /><AlertDescription>Couldn&apos;t load the clinic: {clinic.error.message}</AlertDescription></Alert>
      ) : !clinic.data ? (
        <div className="space-y-4"><Skeleton className="h-9 w-full max-w-2xl" /><Skeleton className="h-72 w-full" /></div>
      ) : (
        // The open tab lives in the URL, so a reload or a shared link lands on it.
        <Tabs value={tab} onValueChange={(t) => router.replace(`${pathname}?tab=${t}`, { scroll: false })}>
          <div className="-mx-4 overflow-x-auto px-4 pb-1 md:mx-0 md:px-0">
            <TabsList>
              {tabs.map((t) => <TabsTrigger key={t.id} value={t.id}>{t.label}</TabsTrigger>)}
            </TabsList>
          </div>
          {tabs.map(({ id, Panel }) => (
            <TabsContent key={id} value={id} className="mt-6">
              {/* Keyed by clinic: switching clinics starts every form fresh. */}
              <Panel key={clinic.data.id} clinic={clinic.data} />
            </TabsContent>
          ))}
        </Tabs>
      )}
    </>
  );
}

export default function SetupPage() {
  return (
    <Suspense>
      <Setup />
    </Suspense>
  );
}
