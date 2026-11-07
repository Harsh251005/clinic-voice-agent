// The signed-out pages' one entrance: fade in while rising a few pixels.
// Stagger with [--tw-animation-delay:…]. Not delay-*/duration-*: those also
// slow hover transitions. motion-safe: viewers who asked their computer for
// less motion see everything at once, still.
export const rise =
  "motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-3 animation-duration-700 ease-out fill-mode-both";

/** The same, coming in from the left: rows inside the Today sketch. */
export const slideIn =
  "motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-left-4 animation-duration-500 ease-out fill-mode-both";
