"use client";
// Light, dark, or the computer's own setting: the viewer's choice, kept in
// this browser. The page's <html data-theme> is what the CSS reads; a tiny
// script in <head> (THEME_SCRIPT) sets it before the first paint, so a dark
// page never flashes white.
import { useEffect, useSyncExternalStore } from "react";

export type ThemeChoice = "light" | "dark" | "system";

const KEY = "clinicdesk.theme";
const DARK = "(prefers-color-scheme: dark)";
const listeners = new Set<() => void>();

export const THEME_SCRIPT = `(function(){var c;try{c=localStorage.getItem(${JSON.stringify(KEY)})}catch(e){}`
  + `var d=c==="dark"||(c!=="light"&&matchMedia(${JSON.stringify(DARK)}).matches);`
  + `document.documentElement.dataset.theme=d?"dark":"light"})()`;

function read(): ThemeChoice {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch { /* storage blocked: follow the computer */ }
  return "system";
}

function resolve(choice: ThemeChoice): "light" | "dark" {
  return choice === "system" ? (matchMedia(DARK).matches ? "dark" : "light") : choice;
}

function subscribe(onChange: () => void) {
  listeners.add(onChange);
  const media = matchMedia(DARK);
  media.addEventListener("change", onChange); // the computer switched, under "system"
  window.addEventListener("storage", onChange); // another tab chose
  return () => {
    listeners.delete(onChange);
    media.removeEventListener("change", onChange);
    window.removeEventListener("storage", onChange);
  };
}

export function setTheme(choice: ThemeChoice) {
  try {
    if (choice === "system") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, choice);
  } catch { /* storage blocked: applies to this page only */ }
  document.documentElement.dataset.theme = resolve(choice);
  listeners.forEach((l) => l());
}

/** [what the viewer chose, what the page shows]. */
export function useTheme(): [ThemeChoice, "light" | "dark"] {
  const choice = useSyncExternalStore(subscribe, read, () => "system" as const);
  const shown = useSyncExternalStore(subscribe, () => resolve(read()), () => "light" as const);
  return [choice, shown];
}

/** Keeps <html data-theme> right when the computer switches under "system". */
export function useThemeSync() {
  const [, shown] = useTheme();
  useEffect(() => {
    document.documentElement.dataset.theme = shown;
  }, [shown]);
}
