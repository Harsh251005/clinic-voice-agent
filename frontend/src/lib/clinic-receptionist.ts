"use client";
// A clinic's own receptionist settings (admins only; Harsh, 2026-11-10):
// voice, speed, pitch, instructions, call length, free times offered.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { keys } from "@/lib/queries";

export type ClinicReceptionist = Schemas["ClinicReceptionistOut"];
export type ClinicReceptionistIn = Schemas["ClinicReceptionistIn"];

const key = (clinicId: number) => ["admin", "clinic-receptionist", clinicId] as const;

export function useClinicReceptionist(clinicId: number) {
  return useQuery({
    queryKey: key(clinicId),
    queryFn: () => unwrap(api.GET("/api/admin/clinics/{clinic_id}/receptionist", { params: { path: { clinic_id: clinicId } } })),
  });
}

export function useSaveClinicReceptionist(clinicId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ClinicReceptionistIn) =>
      unwrap(api.PUT("/api/admin/clinics/{clinic_id}/receptionist", { params: { path: { clinic_id: clinicId } }, body })),
    onSuccess: (page) => {
      qc.setQueryData(key(clinicId), page);
      qc.invalidateQueries({ queryKey: ["admin", "voice"] }); // a new voice changes what is recorded
      qc.invalidateQueries({ queryKey: keys.clinic(clinicId) });
      toast.success("Saved. This clinic's calls use it from the next call.");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}
