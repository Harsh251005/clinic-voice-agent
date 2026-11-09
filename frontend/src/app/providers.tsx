"use client";
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEveryChange, ApiError } from "@/lib/api/client";
import { Toaster } from "@/components/ui/sonner";
import { useThemeSync } from "@/lib/theme";

let browserQueryClient: QueryClient | undefined;

function getQueryClient() {
  const make = () => {
    const client = new QueryClient({
      defaultOptions: {
        queries: {
          staleTime: 30_000,
          // Retrying a 401/403/404/422 can't help; network blips and 5xx can.
          retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 2,
        },
      },
    });
    // Any saved change may have fixed a problem; the API re-checks before it
    // answers, so the bell and banner are asked again at once.
    if (typeof window !== "undefined") afterEveryChange(() => client.invalidateQueries({ queryKey: ["problems"] }));
    return client;
  };
  // Keep server renders isolated; reuse one client in the browser.
  if (typeof window === "undefined") return make();
  browserQueryClient ??= make();
  return browserQueryClient;
}

export function Providers({ children }: { children: ReactNode }) {
  useThemeSync();
  return (
    <QueryClientProvider client={getQueryClient()}>
      {children}
      <Toaster position="top-center" richColors />
    </QueryClientProvider>
  );
}
