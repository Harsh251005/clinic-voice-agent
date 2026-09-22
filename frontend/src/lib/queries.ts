"use client";
// Data hooks: one place that knows the API's paths and cache keys.
import { useQuery } from "@tanstack/react-query";
import { api, ApiError, unwrap, type Schemas } from "@/lib/api/client";

export const keys = {
  me: ["me"] as const,
  clinic: (id: number) => ["clinic", id] as const,
};

/** The signed-in viewer, or null when signed out (a 401 is a state, not an error). */
export function useMe() {
  return useQuery({
    queryKey: keys.me,
    queryFn: async (): Promise<Schemas["Me"] | null> => {
      try {
        return await unwrap(api.GET("/api/me"));
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) return null;
        throw err;
      }
    },
  });
}

export function useClinic(clinicId: number) {
  return useQuery({
    queryKey: keys.clinic(clinicId),
    queryFn: () => unwrap(api.GET("/api/clinics/{clinic_id}", { params: { path: { clinic_id: clinicId } } })),
  });
}
