// The operator's admin panel against the real API: seeded calls (e2e/start-api.sh)
// show as traces without words; a transcript opens only with a logged reason;
// a clinic can be paused and resumed. Sign-in is off, so the viewer is an admin.
import { expect, test } from "@playwright/test";

test("health shows the calls, what went wrong and how fast it answers", async ({ page }) => {
  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: "Health" })).toBeVisible();
  await expect(page.getByText("Operator").first()).toBeVisible();
  await expect(page.getByText(/never finished: the worker may have stopped/)).toBeVisible();
  await expect(page.getByText("sarvam/bulbul:v3: 1 error in 1 call.")).toBeVisible();
  await expect(page.getByText("Caller's wait")).toBeVisible();
});

test("a call's trace has every step and none of the words", async ({ page }) => {
  await page.goto("/admin/calls");
  await expect(page.getByText("Dropped", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: /Booked/ }).click();
  await expect(page.getByRole("heading", { name: "Every step" })).toBeVisible();
  await expect(page.getByText("check_booking")).toBeVisible();
  await expect(page.getByText("book_appointment")).toBeVisible();
  await expect(page.getByText(/Appointment #\d+ booked/)).toBeVisible();
  await expect(page.getByText("कल सुबह डॉक्टर आशा का टाइम है?")).toHaveCount(0);
});

test("the transcript opens only with a reason, and the opening is logged", async ({ page }) => {
  await page.goto("/admin/calls");
  await page.getByRole("link", { name: /Booked/ }).click();
  await page.getByRole("button", { name: "Open for debugging" }).click();
  const open = page.getByRole("button", { name: "Log reason and open" });
  await expect(open).toBeDisabled();
  await page.getByLabel("Reason").fill("Checking what the receptionist heard");
  await open.click();
  await expect(page.getByText("कल सुबह डॉक्टर आशा का टाइम है?")).toBeVisible();
  await expect(page.getByText("“Checking what the receptionist heard”")).toBeVisible();
});

test("errors are grouped by vendor with their calls", async ({ page }) => {
  await page.goto("/admin/errors");
  await expect(page.getByText("sarvam/bulbul:v3")).toBeVisible();
  await expect(page.getByText("Retried", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: /^#\d+$/ })).toHaveCount(1);
});

test("a clinic can be paused, which closes its call link, and resumed", async ({ page, request }) => {
  await page.goto("/admin/clinics");
  await page.getByRole("link", { name: /Demo Family Clinic/ }).click();
  const answers = page.getByRole("switch", { name: "Receptionist answers calls" });
  await expect(answers).toBeChecked();
  await expect(page.getByRole("button", { name: "Delete clinic" })).toBeDisabled();
  await answers.click();
  await expect(page.getByText("Paused").first()).toBeVisible();
  const paused = await request.get("http://127.0.0.1:8095/call/demo-family-clinic");
  expect(paused.status()).toBe(503);
  await answers.click();
  await expect(page.getByText("Taking calls").first()).toBeVisible();
  expect((await request.get("http://127.0.0.1:8095/call/demo-family-clinic")).status()).toBe(200);
});
