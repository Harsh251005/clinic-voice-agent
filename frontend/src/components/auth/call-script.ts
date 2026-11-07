// The example call the sign-in page plays on a loop. It shows only what the
// receptionist really does: says it is automated, finds a free slot, reads the
// booking back, and books once the caller says yes. Keep it that way.
// Romanised Hindi on purpose (Harsh, 2026-11-07): anyone can read it. This is
// only the page's display; the real receptionist writes Devanagari for its voice.
export type Speaker = "agent" | "caller";
export type Line = { who: Speaker; text: string };

export const CALL: Line[] = [
  { who: "agent", text: "Namaste! Main clinic ki automated assistant hoon. Bataiye, kaise madad karoon?" },
  { who: "caller", text: "Kal subah doctor se milna hai." },
  { who: "agent", text: "Kal subah 10:30 khaali hai. 10:30 book kar doon?" },
  { who: "caller", text: "Haan, kar dijiye." },
];

export const BOOKED = { title: "Appointment booked", detail: "Tomorrow · 10:30 AM" };
