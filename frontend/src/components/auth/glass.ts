// The look shared by every card on the dark signed-out canvas: frosted glass,
// a thin teal light along the top edge, and two button styles. Fixed colours,
// not theme tokens: these pages look the same for every viewer.
export const glassCard =
  "relative rounded-2xl bg-gradient-to-b from-white/[0.09] to-white/[0.03] p-8 text-white shadow-[0_40px_100px_-30px_rgba(0,0,0,0.7)] ring-1 ring-white/10 backdrop-blur-xl";

export const glassEdge =
  "pointer-events-none absolute inset-x-10 -top-px h-px bg-gradient-to-r from-transparent via-teal-300/70 to-transparent";

/** The logo tile on the dark canvas: bright teal with a soft glow. */
export const glassMark =
  "bg-gradient-to-br from-teal-300 to-teal-600 text-white ring-1 ring-white/25 shadow-[0_0_32px_-6px_rgba(45,212,191,0.7)]";

/** The one bright action on a card. */
export const glassPrimary =
  "h-11 w-full rounded-lg border-transparent bg-white text-sm font-medium text-slate-900 hover:bg-white/90";

/** A quieter action: outlined glass. */
export const glassQuiet =
  "h-11 w-full rounded-lg border-white/15 bg-white/5 text-sm font-medium text-white hover:bg-white/10 hover:text-white";
