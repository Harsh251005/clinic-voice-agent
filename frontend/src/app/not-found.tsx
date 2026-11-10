// Any address the dashboard doesn't have, in the same look as the other
// full-page states (never the framework's default 404 page).
import type { Metadata } from "next";
import { PageNotFound } from "@/components/app/gates";

export const metadata: Metadata = { title: "Page not found" };

export default function NotFound() {
  return <PageNotFound />;
}
