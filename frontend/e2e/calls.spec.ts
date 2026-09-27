// The clinic's own Calls page against the real API: seeded calls
// (e2e/start-api.sh) read in plain words, what was said without the tools
// the receptionist used, and a note whenever ClinicDesk support opened one.
import { expect, test } from "@playwright/test";

const CALLS = "/clinics/1/calls";

test("calls are listed in plain words, from the sidebar", async ({ page }) => {
  await page.goto("/clinics/1/today");
  await page.getByRole("link", { name: "Calls" }).first().click();
  await expect(page).toHaveURL(/\/clinics\/1\/calls$/);
  await expect(page.getByText(/^Booked Riya Sharma with Dr\. Asha Mehta/)).toBeVisible();
  await expect(page.getByText("The caller asked a question")).toBeVisible();
  await expect(page.getByText("The call was cut off. The caller may not have been helped.")).toBeVisible();
  await expect(page.getByText(/sarvam|openai|vendor/i)).toHaveCount(0);
});

test("a call shows what was said and nothing technical", async ({ page }) => {
  await page.goto(CALLS);
  await page.getByRole("link", { name: /Booked Riya Sharma/ }).click();
  await expect(page.getByRole("heading", { name: "What was said" })).toBeVisible();
  await expect(page.getByText("कल सुबह डॉक्टर आशा का टाइम है?")).toBeVisible();
  await expect(page.getByText("हाँ, सही है")).toBeVisible();
  await expect(page.getByText("check_booking")).toHaveCount(0);
  await expect(page.getByText("Not booked yet.")).toHaveCount(0);
  await page.getByRole("link", { name: /\d{1,2}:\d{2} (am|pm)/ }).click(); // the visit, in the diary
  await expect(page).toHaveURL(/\/clinics\/1\/appointments\?day=\d{4}-\d{2}-\d{2}/);
});

test("the clinic sees when support opened a call, and why", async ({ page }) => {
  await page.goto("/admin/calls");
  await page.getByRole("link", { name: /Question only/ }).click();
  await page.getByRole("button", { name: "Open for debugging" }).click();
  await page.getByLabel("Reason").fill("Receptionist answered slowly");
  await page.getByRole("button", { name: "Log reason and open" }).click();
  await expect(page.getByText("पार्किंग है क्या?")).toBeVisible();

  await page.goto(CALLS);
  await page.getByRole("link", { name: /The caller asked a question/ }).click();
  await expect(page.getByRole("heading", { name: "Viewed by ClinicDesk support" })).toBeVisible();
  await expect(page.getByText("“Receptionist answered slowly”")).toBeVisible();
});
