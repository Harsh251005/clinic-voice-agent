"use client";
// "/": sign in, or go to a clinic (the last one opened, else the first).
import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { FullPageLoading, LoadError, NoClinic, SignIn } from "@/components/app/gates";
import { lastClinic } from "@/lib/last-clinic";
import { useMe } from "@/lib/queries";

function Home() {
  const me = useMe();
  const router = useRouter();
  const problem = useSearchParams().get("signin");

  const target = (() => {
    if (!me.data) return null;
    const { clinics, is_admin } = me.data;
    const last = lastClinic();
    if (last && clinics.some((c) => c.id === last)) return `/clinics/${last}/today`;
    if (clinics.length) return `/clinics/${clinics[0].id}/today`;
    return is_admin ? "/new-clinic" : null;
  })();

  useEffect(() => {
    if (target) router.replace(target);
  }, [target, router]);

  if (me.isError) return <LoadError onRetry={() => me.refetch()} />;
  if (me.data === null) return <SignIn problem={problem} />;
  if (me.data && !target) return <NoClinic email={me.data.email} />;
  return <FullPageLoading />;
}

export default function Page() {
  return (
    <Suspense fallback={<FullPageLoading />}>
      <Home />
    </Suspense>
  );
}
