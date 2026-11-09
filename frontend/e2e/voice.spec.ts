// Voice & phrases against the real API. The e2e API has no voice key
// (e2e/start-api.sh), so nothing can be recorded: every line is said live,
// and the page says why. Editing and the greeting rule work without one.
import { expect, test } from "@playwright/test";

test("every fixed line is listed, said live while there is no voice", async ({ page }) => {
  await page.goto("/admin/voice");
  await expect(page.getByRole("heading", { name: "Voice & phrases" })).toBeVisible();
  await expect(page.getByText(/No voice to record with: .*SARVAM_API_KEY/)).toBeVisible();
  for (const title of ["Greeting", "“One moment” lines", "Goodbye", "Time-limit goodbye"]) {
    await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();
  }
  await expect(page.getByText("Said live").first()).toBeVisible();
  await expect(page.getByRole("button", { name: /^Record/ })).toHaveCount(0);
});

test("a line is changed in English and Hindi, then put back", async ({ page }) => {
  await page.goto("/admin/voice");
  await page.getByRole("button", { name: "Change Line 3" }).click();
  await page.getByLabel("In English").fill("Just a moment, please.");
  await page.getByLabel("What she says (Hindi)").fill("बस एक पल जी।");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("बस एक पल जी।")).toBeVisible();
  await expect(page.getByText("Just a moment, please.")).toBeVisible();

  await page.getByRole("button", { name: "Change Line 3" }).click();
  await page.getByLabel("In English").fill("Yes, just one second.");
  await page.getByLabel("What she says (Hindi)").fill("जी, बस एक सेकंड।");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("बस एक पल जी।")).toHaveCount(0);
});

test("a greeting that stops saying it is automated is refused", async ({ page }) => {
  await page.goto("/admin/voice");
  await page.getByRole("button", { name: "Change Shared greeting" }).click();
  await page.getByLabel("What she says (Hindi)").fill("नमस्ते, {clinic} में स्वागत है।");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("alert")).toContainText("automated assistant");
  await page.getByRole("button", { name: "Cancel" }).click();
});

test("a clinic gets its own greeting and goes back to the shared one", async ({ page }) => {
  await page.goto("/admin/voice");
  await page.getByRole("button", { name: "Give Demo Family Clinic its own greeting" }).click();
  await expect(page.getByLabel("What she says (Hindi)")).toHaveValue(/ऑटोमेटेड असिस्टेंट/);
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Demo Family Clinic's own greeting")).toBeVisible();
  await page.getByRole("button", { name: "Demo Family Clinic: use the shared greeting" }).click();
  await expect(page.getByText("Demo Family Clinic's own greeting")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Give Demo Family Clinic its own greeting" })).toBeVisible();
});
