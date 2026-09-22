/** "98765 43210" for a ten-digit Indian mobile, as staff read it aloud. */
export function formatPhone(phone: string): string {
  return /^\d{10}$/.test(phone) ? `${phone.slice(0, 5)} ${phone.slice(5)}` : phone;
}
