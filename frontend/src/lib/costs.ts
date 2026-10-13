"use client";
// What the service costs the operator: data hooks and the words for it.
// Money is worked out by the API from each call's exact usage and the price
// list edited on the Prices screen.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, unwrap, type Schemas } from "@/lib/api/client";

export const costKeys = {
  month: (month: string | null) => ["admin", "costs", month] as const,
  settings: ["admin", "cost-settings"] as const,
};

export function useCostMonth(month: string | null) {
  return useQuery({
    queryKey: costKeys.month(month),
    queryFn: () => unwrap(api.GET("/api/admin/costs", { params: { query: month ? { month } : {} } })),
    refetchInterval: 60_000,
  });
}

export function useCostSettings() {
  return useQuery({
    queryKey: costKeys.settings,
    queryFn: () => unwrap(api.GET("/api/admin/cost-settings")),
  });
}

export type CostKind = "prices" | "rates" | "allowances" | "fixed" | "bills";
type Bodies = {
  prices: Schemas["PriceIn"];
  rates: Schemas["RateIn"];
  allowances: Schemas["AllowanceIn"];
  fixed: Schemas["FixedIn"];
  bills: Schemas["BillIn"];
};

/** Add (no id), change or remove one row of the price list and the rest.
 *  Every cost figure depends on them, so all of costs is refreshed. */
export function useCostRow<K extends CostKind>(kind: K) {
  const qc = useQueryClient();
  const done = (message: string) => {
    toast.success(message);
    qc.invalidateQueries({ queryKey: ["admin"] });
  };
  const save = useMutation({
    mutationFn: ({ id, body }: { id?: number; body: Bodies[K] }) => {
      // The paths differ only by kind; openapi-fetch needs each spelt out to type it.
      const path = `/api/admin/cost-settings/${kind}` as "/api/admin/cost-settings/prices";
      const withId = `${path}/{row_id}` as "/api/admin/cost-settings/prices/{row_id}";
      const b = body as Schemas["PriceIn"];
      return id == null
        ? unwrap(api.POST(path, { body: b }))
        : unwrap(api.PUT(withId, { params: { path: { row_id: id } }, body: b }));
    },
    onSuccess: (_d, { id }) => done(id == null ? "Added." : "Saved."),
    onError: (e) => toast.error(e.message),
  });
  const remove = useMutation({
    mutationFn: (id: number) => {
      const withId = `/api/admin/cost-settings/${kind}/{row_id}` as "/api/admin/cost-settings/prices/{row_id}";
      return unwrap(api.DELETE(withId, { params: { path: { row_id: id } } }));
    },
    onSuccess: () => done("Removed."),
    onError: (e) => toast.error(e.message),
  });
  return { save, remove };
}

// ---------- words ----------

const INR = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** ₹4.20; a cost too small to show in paise says so rather than "₹0.00". */
export function rupees(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n > 0 && n < 0.005) return "under ₹0.01";
  return INR.format(n);
}

export function money(amount: number, currency: string): string {
  if (currency === "INR") return rupees(amount);
  return new Intl.NumberFormat("en-US", { style: "currency", currency, maximumFractionDigits: 4 }).format(amount);
}

export function quantity(n: number): string {
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: n < 10 ? 2 : 0 }).format(n);
}

const SINGULAR: Record<string, string> = { seconds_heard: "second heard", characters: "character spoken", minutes: "call minute" };

/** Matches the API's costs.per_text: "million words read (tokens)", "hour heard", "call minute". */
export function perText(per: number, unit: string, units: Record<string, string>): string {
  const words = units[unit] ?? unit;
  if (unit === "seconds_heard" && per === 3600) return "hour heard";
  if (per === 1) return SINGULAR[unit] ?? words;
  if (per === 1_000_000) return `million ${words}`;
  return `${new Intl.NumberFormat("en-US").format(per)} ${words}`;
}

export const VENDORS: Record<string, string> = {
  sarvam: "Sarvam", elevenlabs: "ElevenLabs", openai: "OpenAI", livekit: "LiveKit",
};

export const PARTS: Record<string, string> = {
  listening: "Listening",
  thinking: "Thinking",
  speaking: "Speaking",
  call_line: "Call line",
  other: "Other",
};

export function monthName(month: string): string {
  const [y, m] = month.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString("en-IN", { month: "long", year: "numeric" });
}
