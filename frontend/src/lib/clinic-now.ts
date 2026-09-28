"use client";
import { useEffect, useState, useSyncExternalStore } from "react";
import { nowIn } from "@/lib/dates";

/** The clinic's clock, ticking once a minute so "now", "next" and "open" stay true. */
export function useClinicNow(timezone: string | undefined) {
  const [now, setNow] = useState(() => (timezone ? nowIn(timezone) : null));
  useEffect(() => {
    if (!timezone) return;
    const tick = () => setNow(nowIn(timezone));
    tick();
    const id = setInterval(tick, 60_000);
    return () => clearInterval(id);
  }, [timezone]);
  return now;
}

/** True while the screen is at least this wide: pick one layout instead of
 *  rendering both and hiding one (a hidden copy still answers to tests and
 *  screen readers). False on the server. */
export function useWide(minWidth = 768) {
  const query = `(min-width: ${minWidth}px)`;
  return useSyncExternalStore(
    (onChange) => {
      const list = window.matchMedia(query);
      list.addEventListener("change", onChange);
      return () => list.removeEventListener("change", onChange);
    },
    () => window.matchMedia(query).matches,
    () => false,
  );
}
