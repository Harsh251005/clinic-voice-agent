// The example call the sign-in page plays on a loop. It shows only what the
// receptionist really does: says it is automated, finds a free slot, reads the
// booking back, and books once the caller says yes. Keep it that way.
export type Speaker = "agent" | "caller";
export type Line = { who: Speaker; text: string };

export const CALL: Line[] = [
  { who: "agent", text: "नमस्ते! मैं क्लिनिक की ऑटोमेटेड असिस्टेंट हूँ। बताइए, कैसे मदद करूँ?" },
  { who: "caller", text: "कल सुबह डॉक्टर से मिलना है।" },
  { who: "agent", text: "कल सुबह 10:30 खाली है। 10:30 बुक कर दूँ?" },
  { who: "caller", text: "हाँ, कर दीजिए।" },
];

export const BOOKED = { title: "Appointment booked", detail: "Tomorrow · 10:30 AM" };
