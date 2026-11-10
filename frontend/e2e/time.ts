// The dashboard's 12-hour time field (src/components/ui/time-field.tsx):
// three pickers under one name. Tests still speak "HH:MM".
import { expect, type Page } from "@playwright/test";

const field = (page: Page, label: string) => page.getByRole("group", { name: label, exact: true });

/** Pick a time, as staff would: hour, then minutes, then am or pm. */
export async function setTime(page: Page, label: string, hhmm: string) {
  const [h, m] = hhmm.split(":").map(Number);
  await field(page, label).getByLabel(`${label}: hour`).selectOption(String(((h + 11) % 12) + 1));
  await field(page, label).getByLabel(`${label}: minutes`).selectOption(String(m));
  await field(page, label).getByLabel(`${label}: am or pm`).selectOption(h >= 12 ? "pm" : "am");
}

export async function expectTime(page: Page, label: string, hhmm: string) {
  await expect(field(page, label)).toHaveAttribute("data-value", hhmm);
}
