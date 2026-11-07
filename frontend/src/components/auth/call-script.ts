// The example call the sign-in page plays on a loop. It follows the real
// booking order in clinic_agent/prompts.py: greet and say it is automated,
// offer free times, take the patient's name and mobile number, ask the reason,
// read everything back, and book only after a clear yes. Change it with them.
// Romanised Hindi on purpose (Harsh, 2026-11-07): anyone can read it. This is
// only the page's display; the real receptionist writes Devanagari for its voice.
export type Speaker = "agent" | "caller";
export type Line = { who: Speaker; text: string };

export const CALL: Line[] = [
  { who: "agent", text: "Namaste ji, clinic mein aapka swagat hai. Main yahan ki automated assistant hoon. Bataiye, kaise madad karoon?" },
  { who: "caller", text: "Kal subah doctor se milna hai." },
  { who: "agent", text: "Kal subah 10 baje aur 10:30 khaali hain. Kaunsa time theek rahega?" },
  { who: "caller", text: "10:30 theek hai." },
  { who: "agent", text: "Ji. Patient ka naam aur das ank ka mobile number bata dijiye." },
  { who: "caller", text: "Riya Sharma. 98200 12345." },
  { who: "agent", text: "Kis takleef ke liye dikhana hai?" },
  { who: "caller", text: "Do din se bukhar hai." },
  { who: "agent", text: "Toh kal subah 10:30, Dr. Mehta ke saath, Riya Sharma, number 98200 12345. Sab sahi hai na?" },
  { who: "caller", text: "Haan, sab sahi hai." },
  { who: "agent", text: "Aapka appointment book ho gaya hai. Dhanyavaad!" },
];

export const BOOKED = { title: "Appointment booked", detail: "Riya Sharma · Dr. Mehta · Tomorrow, 10:30 AM" };
