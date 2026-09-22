import { redirect } from "next/navigation";

export default async function ClinicHome({ params }: PageProps<"/clinics/[clinicId]">) {
  const { clinicId } = await params;
  redirect(`/clinics/${clinicId}/appointments`);
}
