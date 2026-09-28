// The appointments diary: book by clicking a free slot, mark visits, find a
// patient, the week at a glance, and the phone layout. Runs after
// dashboard.spec.ts on the same database (Riya Sharma is booked today at 10).
import { expect, test } from "@playwright/test";

const DIARY = "/clinics/1/appointments";

/** A Tuesday at least a day ahead in the clinic's timezone: Dr. Asha sits
 *  10 am–1 pm and 5–8 pm, every slot still in the future. */
function nextTuesday(): string {
  const today = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata" }).format(new Date());
  const d = new Date(`${today}T00:00:00Z`);
  do d.setUTCDate(d.getUTCDate() + 1); while (d.getUTCDay() !== 2);
  return d.toISOString().slice(0, 10);
}

test("clicking a free slot books exactly there", async ({ page }) => {
  await page.goto(`${DIARY}?day=${nextTuesday()}`);
  await expect(page.getByRole("region", { name: "Day diary" })).toContainText("10 am–1 pm, 5–8 pm");
  await page.getByRole("button", { name: "Book Dr. Asha Mehta at 10:30 am" }).click();
  await expect(page.getByLabel("Time", { exact: true })).toHaveValue("10:30");
  await page.getByLabel("Patient name").fill("Kabir Rao");
  await page.getByLabel("Mobile number").fill("9819044444");
  await page.getByRole("button", { name: "Book appointment" }).click();
  await expect(page.getByText(/^Booked: Kabir Rao with Dr. Asha Mehta/)).toBeVisible();
  await expect(page.getByRole("button", { name: /^10:30 am, Kabir Rao, Booked, by staff/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Book Dr. Asha Mehta at 10:30 am" })).toHaveCount(0);
});

test("a future visit can't be marked yet", async ({ page }) => {
  await page.goto(`${DIARY}?day=${nextTuesday()}`);
  await page.getByRole("button", { name: /Kabir Rao/ }).click();
  await expect(page.getByRole("menuitem", { name: "Edit" })).toBeVisible();
  await expect(page.getByRole("menuitem", { name: "Arrived" })).toHaveCount(0);
});

test("marking a visit: arrived, then done, then cleared", async ({ page }) => {
  await page.goto(DIARY);
  await page.getByRole("button", { name: /Riya Sharma/ }).click();
  await page.getByRole("menuitem", { name: "Arrived" }).click();
  await expect(page.getByText("Riya Sharma: arrived.")).toBeVisible();
  await expect(page.getByRole("button", { name: /Riya Sharma, Arrived/ })).toBeVisible();

  await page.getByRole("button", { name: /Riya Sharma/ }).click();
  await page.getByRole("menuitem", { name: "Done" }).click();
  await expect(page.getByRole("button", { name: /Riya Sharma, Done/ })).toBeVisible();
  await expect(page.getByText("1 done")).toBeVisible();

  await page.goto("/clinics/1/today");
  await expect(page.getByRole("heading", { name: "Doctors today" })).toBeVisible();
  await expect(page.getByText("Done", { exact: true })).toBeVisible();

  await page.goto(DIARY);
  await page.getByRole("button", { name: /Riya Sharma/ }).click();
  await page.getByRole("menuitem", { name: "Clear mark" }).click();
  await expect(page.getByRole("button", { name: /Riya Sharma, Booked/ })).toBeVisible();
});

test("finding a patient by the last digits of their number", async ({ page }) => {
  await page.goto(DIARY);
  await page.getByRole("searchbox", { name: /Find a patient/ }).fill("12345");
  await expect(page).toHaveURL(/q=12345/);
  await expect(page.getByRole("status")).toHaveText("1 found");
  await expect(page.getByText("Riya Sharma")).toBeVisible();
  await page.getByRole("button", { name: "Open day" }).click();
  await expect(page).not.toHaveURL(/q=/);
  await expect(page.getByRole("button", { name: /Riya Sharma/ })).toBeVisible();

  await page.getByRole("searchbox", { name: /Find a patient/ }).fill("Nobody Here");
  await expect(page.getByText(/No appointments for .Nobody Here./)).toBeVisible();
});

test("the week at a glance opens any day", async ({ page }) => {
  await page.goto(`${DIARY}?day=${nextTuesday()}`);
  await page.getByRole("button", { name: "Week", exact: true }).click();
  await expect(page).toHaveURL(/view=week/);
  const cell = page.getByRole("button", { name: /^Dr. Asha Mehta, Tue .*: 1 booked, \d+ free$/ });
  await expect(cell).toContainText("Kabir Rao");
  await expect(page.getByRole("button", { name: /^Dr. Asha Mehta, Sun .*: Not in$/ })).toBeVisible();
  await cell.click();
  await expect(page).not.toHaveURL(/view=week/);
  await expect(page.getByRole("button", { name: /Kabir Rao/ })).toBeVisible();
});

test.describe("on a phone", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("one doctor at a time, and free times are tap targets", async ({ page }) => {
    await page.goto(`${DIARY}?day=${nextTuesday()}`);
    await expect(page.getByRole("region", { name: "Day diary" })).toHaveCount(0);
    await expect(page.getByRole("tab", { name: /Dr. Asha Mehta/ })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("button", { name: /10:30 am, Kabir Rao/ })).toBeVisible();
    await page.getByRole("button", { name: "Book Dr. Asha Mehta at 10:45 am" }).click();
    await expect(page.getByLabel("Time", { exact: true })).toHaveValue("10:45");
    await page.keyboard.press("Escape");
    await page.getByRole("tab", { name: /Dr. Rohan Iyer/ }).click();
    await expect(page.getByRole("heading", { name: "Dr. Rohan Iyer" })).toBeVisible();
    await expect(page.getByRole("button", { name: /Kabir Rao/ })).toHaveCount(0);  // Dr. Asha's patient
  });
});
