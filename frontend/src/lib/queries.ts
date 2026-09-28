"use client";
// Data hooks: one place that knows the API's paths and cache keys.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, ApiError, unwrap, type Schemas } from "@/lib/api/client";

export const keys = {
  me: ["me"] as const,
  clinic: (id: number) => ["clinic", id] as const,
  appointments: (id: number) => ["appointments", id] as const,
  calls: (id: number) => ["calls", id] as const,
  problems: (id: number | "admin") => ["problems", id] as const,
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

export function useDay(clinicId: number, day: string, includeCancelled: boolean) {
  return useQuery({
    queryKey: [...keys.appointments(clinicId), day, includeCancelled],
    queryFn: () =>
      unwrap(api.GET("/api/clinics/{clinic_id}/appointments", {
        params: { path: { clinic_id: clinicId }, query: { day, include_cancelled: includeCancelled } },
      })),
    placeholderData: (previous) => previous, // keep the last day on screen while the next loads
    refetchInterval: 30_000, // bookings from calls appear without a reload
  });
}

/** Seven days from `start`: booked appointments and each doctor's day. */
export function useWeek(clinicId: number, start: string) {
  return useQuery({
    queryKey: [...keys.appointments(clinicId), "week", start],
    queryFn: () => unwrap(api.GET("/api/clinics/{clinic_id}/appointments/week", {
      params: { path: { clinic_id: clinicId }, query: { start } },
    })),
    enabled: !!start,
    placeholderData: (previous) => previous,
    refetchInterval: 30_000,
  });
}

/** Appointments by patient name or number (2+ characters), upcoming first. */
export function useAppointmentSearch(clinicId: number, q: string) {
  return useQuery({
    queryKey: [...keys.appointments(clinicId), "search", q],
    queryFn: () => unwrap(api.GET("/api/clinics/{clinic_id}/appointments/search", {
      params: { path: { clinic_id: clinicId }, query: { q } },
    })),
    enabled: q.trim().length >= 2,
    placeholderData: (previous) => previous,
  });
}

/** A clinic's calls, newest first, a page (50) at a time. */
export function useClinicCalls(clinicId: number, beforeId?: number) {
  return useQuery({
    queryKey: [...keys.calls(clinicId), beforeId ?? null],
    queryFn: () => unwrap(api.GET("/api/clinics/{clinic_id}/calls", {
      params: { path: { clinic_id: clinicId }, query: { before_id: beforeId } },
    })),
    refetchInterval: beforeId ? false : 30_000, // new calls appear without a reload
  });
}

/** Today's calls in the clinic's timezone: counts, and callers who may not have been helped. */
export function useCallsToday(clinicId: number) {
  return useQuery({
    queryKey: [...keys.calls(clinicId), "today"],
    queryFn: () => unwrap(api.GET("/api/clinics/{clinic_id}/calls/today", { params: { path: { clinic_id: clinicId } } })),
    refetchInterval: 30_000,
  });
}

/** One call with what was said: the caller and the receptionist only. */
export function useClinicCall(clinicId: number, callId: number) {
  return useQuery({
    queryKey: [...keys.calls(clinicId), "call", callId],
    queryFn: () => unwrap(api.GET("/api/clinics/{clinic_id}/calls/{call_id}", {
      params: { path: { clinic_id: clinicId, call_id: callId } },
    })),
  });
}

// Problems keep refreshing in a background tab too: the tab title and desktop
// alerts are how a problem reaches someone working in another window.
const PROBLEMS_EVERY = { refetchInterval: 30_000, refetchIntervalInBackground: true } as const;

/** This clinic's open problems (and the last week's), in plain words. */
export function useProblems(clinicId: number, enabled = true) {
  return useQuery({
    queryKey: keys.problems(clinicId),
    queryFn: () => unwrap(api.GET("/api/clinics/{clinic_id}/problems", { params: { path: { clinic_id: clinicId } } })),
    enabled,
    ...PROBLEMS_EVERY,
  });
}

/** Every problem across clinics and the system, for the operator. */
export function useAdminProblems(enabled = true) {
  return useQuery({
    queryKey: keys.problems("admin"),
    queryFn: () => unwrap(api.GET("/api/admin/problems")),
    enabled,
    ...PROBLEMS_EVERY,
  });
}

/** "Seen": folds a warning into the bell. On the clinic's side or the operator's. */
export function useSeenProblem(scope: number | "admin") {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => unwrap(scope === "admin"
      ? api.POST("/api/admin/problems/{problem_id}/seen", { params: { path: { problem_id: id } } })
      : api.POST("/api/clinics/{clinic_id}/problems/{problem_id}/seen", { params: { path: { clinic_id: scope, problem_id: id } } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.problems(scope) }),
    onError: (err) => toast.error(err.message),
  });
}

export function usePatterns() {
  return useQuery({
    queryKey: ["hour-patterns"],
    queryFn: () => unwrap(api.GET("/api/hours/patterns")),
    staleTime: Infinity, // fixed in code
  });
}

/** A change to a clinic: toast on success, the API's own message on failure,
 *  then refresh the clinic (and the viewer's clinic list, for renames). */
export function useClinicChange<TArgs, TResult>(
  clinicId: number,
  change: (args: TArgs) => Promise<TResult>,
  success?: string | ((result: TResult, args: TArgs) => string),
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: change,
    onSuccess: (result, args) => {
      if (success) toast.success(typeof success === "string" ? success : success(result, args));
      return Promise.all([
        queryClient.invalidateQueries({ queryKey: keys.clinic(clinicId) }),
        queryClient.invalidateQueries({ queryKey: keys.me }),
      ]);
    },
    onError: (err) => toast.error(err.message),
  });
}
