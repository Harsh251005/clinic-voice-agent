import { AppShell } from "@/components/app/app-shell";

export default async function ClinicLayout({ children, params }: LayoutProps<"/clinics/[clinicId]">) {
  const { clinicId } = await params;
  return <AppShell clinicId={Number(clinicId)}>{children}</AppShell>;
}
