"use client";
// One clinic, as the operator sees it: taking calls or paused, recent calls,
// who can sign in, and deleting it. Its patients are not here.
import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { AlertCircle, ArrowLeft, PhoneCall, Settings2, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { ActiveBadge, Stat } from "@/components/admin/bits";
import { Team } from "@/components/setup/team";
import { adminKeys, useAdminClinics, when } from "@/lib/admin";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { keys, useClinic } from "@/lib/queries";

export default function AdminClinicPage() {
  const clinicId = Number(useParams<{ clinicId: string }>().clinicId);
  const clinics = useAdminClinics();
  const details = useClinic(clinicId);
  const c = clinics.data?.find((x) => x.id === clinicId);

  return (
    <div className="space-y-6">
      <Link href="/admin/clinics" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" aria-hidden /> All clinics
      </Link>
      {clinics.isError ? (
        <Alert variant="destructive"><AlertCircle /><AlertDescription>{clinics.error.message}</AlertDescription></Alert>
      ) : !clinics.data ? (
        <Skeleton className="h-40" />
      ) : !c ? (
        <Alert><AlertCircle /><AlertDescription>This clinic doesn&apos;t exist (it may have been deleted).</AlertDescription></Alert>
      ) : (
        <>
          <header className="flex flex-wrap items-center justify-between gap-4">
            <div className="space-y-1.5">
              <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">{c.name}</h1>
              <ActiveBadge active={c.active} />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" asChild><Link href={`/admin/calls?clinic=${c.id}`}><PhoneCall /> Its calls</Link></Button>
              <Button variant="outline" asChild><Link href={`/clinics/${c.id}/setup`}><Settings2 /> Clinic settings</Link></Button>
            </div>
          </header>

          <div className="grid grid-cols-3 divide-x overflow-hidden rounded-xl border bg-card">
            <Stat label="Calls, 7 days" value={c.calls_7d} />
            <Stat label="With vendor errors" value={c.calls_with_errors_7d} tone={c.calls_with_errors_7d ? "bad" : undefined} />
            <Stat label="Last call" value={<span className="text-base sm:text-lg">{c.last_call_at ? when(c.last_call_at) : "None yet"}</span>} />
          </div>

          <Pause c={c} />
          {details.data ? <Team clinic={details.data} /> : <Skeleton className="h-32" />}
          <DeleteClinic c={c} />
        </>
      )}
    </div>
  );
}

function useRefresh() {
  const queryClient = useQueryClient();
  return () => Promise.all([
    queryClient.invalidateQueries({ queryKey: adminKeys.all }),
    queryClient.invalidateQueries({ queryKey: keys.me }),
  ]);
}

function Pause({ c }: { c: Schemas["AdminClinic"] }) {
  const refresh = useRefresh();
  const [busy, setBusy] = useState(false);
  const toggle = async (active: boolean) => {
    setBusy(true);
    try {
      await unwrap(api.PUT("/api/admin/clinics/{clinic_id}/active", { params: { path: { clinic_id: c.id } }, body: { active } }));
      await refresh();
      toast.success(active ? `${c.name} is taking calls again.` : `${c.name} is paused. Its call link now says it isn't taking calls.`);
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="flex items-start justify-between gap-4 rounded-xl border bg-card p-5">
      <div>
        <Label htmlFor="active" className="text-base font-semibold">Receptionist answers calls</Label>
        <p className="mt-1 max-w-xl text-sm text-muted-foreground">
          Pause it to stop all calls, for example when the clinic stops paying or asks for a break. Its data stays;
          callers see &quot;not taking calls here right now&quot; and the clinic&apos;s phone number.
        </p>
      </div>
      <Switch id="active" checked={c.active} disabled={busy} onCheckedChange={toggle} />
    </section>
  );
}

function DeleteClinic({ c }: { c: Schemas["AdminClinic"] }) {
  const router = useRouter();
  const refresh = useRefresh();
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);

  const remove = async () => {
    setBusy(true);
    try {
      await unwrap(api.DELETE("/api/admin/clinics/{clinic_id}", { params: { path: { clinic_id: c.id } }, body: { confirm_name: typed } }));
      toast.success(`${c.name} and all its data were deleted.`);
      router.push("/admin/clinics");
      await refresh();
    } catch (err) {
      toast.error((err as Error).message);
      setBusy(false);
    }
  };

  return (
    <section className="rounded-xl border border-destructive/30 bg-card p-5">
      <h2 className="font-semibold text-destructive">Delete this clinic</h2>
      <p className="mt-1 max-w-xl text-sm text-muted-foreground">
        Removes the clinic and everything in it for good: doctors, patients, appointments, call records and its team.
        {c.active && " Pause it first."}
      </p>
      <Button variant="destructive" className="mt-4" disabled={c.active} onClick={() => { setTyped(""); setOpen(true); }}>
        <Trash2 /> Delete clinic
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete {c.name}?</DialogTitle>
            <DialogDescription>This can&apos;t be undone. Type the clinic&apos;s name to confirm.</DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="confirm">Clinic name</Label>
            <Input id="confirm" value={typed} onChange={(e) => setTyped(e.target.value)} placeholder={c.name} autoComplete="off" />
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpen(false)}>Keep it</Button>
            <Button variant="destructive" disabled={busy || typed.trim() !== c.name} onClick={remove}>Delete for good</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
