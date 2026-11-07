"use client";
// Plays the example call step by step, forever: each line appears as its
// speaker talks (loud waveform), a short pause, the next line; then the
// booking, a slow fade, and it starts over.
// Viewers who ask for less motion get the finished call, still.
import { useEffect, useState, useSyncExternalStore } from "react";
import { CALL, type Speaker } from "./call-script";

type Step = { shown: number; speaking: Speaker | null; booked: boolean; leaving: boolean; ms: number };

const STEPS: Step[] = [
  { shown: 0, speaking: null, booked: false, leaving: false, ms: 600 }, // empty, fading back in
  ...CALL.flatMap((line, i): Step[] => [
    { shown: i + 1, speaking: line.who, booked: false, leaving: false, ms: 500 + line.text.length * 12 },
    { shown: i + 1, speaking: null, booked: false, leaving: false, ms: 350 },
  ]),
  { shown: CALL.length, speaking: null, booked: true, leaving: false, ms: 2800 },
  { shown: CALL.length, speaking: null, booked: true, leaving: true, ms: 1000 }, // the fade (700 ms) + a beat
];

const STILL: Step = { shown: CALL.length, speaking: null, booked: true, leaving: false, ms: 0 };

const QUERY = "(prefers-reduced-motion: reduce)";
function useReducedMotion() {
  return useSyncExternalStore(
    (onChange) => {
      const m = window.matchMedia(QUERY);
      m.addEventListener("change", onChange);
      return () => m.removeEventListener("change", onChange);
    },
    () => window.matchMedia(QUERY).matches,
    () => false,
  );
}

export function useCallLoop() {
  const reduced = useReducedMotion();
  const [index, setIndex] = useState(0);
  const [cycle, setCycle] = useState(0); // restarts the on-screen call timer

  useEffect(() => {
    if (reduced) return;
    const t = setTimeout(() => {
      const next = (index + 1) % STEPS.length;
      if (next === 0) setCycle((c) => c + 1);
      setIndex(next);
    }, STEPS[index].ms);
    return () => clearTimeout(t);
  }, [index, reduced]);

  return { ...(reduced ? STILL : STEPS[index]), cycle, reduced };
}
