// Admin > Receptionist against the real API (Harsh, 2026-11-10): the shared
// rules and settings are edited, saved, kept on reload, and put back.
import { expect, test } from "@playwright/test";

test("the main rules are edited, kept, and reset to the default", async ({ page }) => {
  await page.goto("/admin/receptionist");
  await expect(page.getByRole("heading", { name: "Receptionist" })).toBeVisible();
  const rules = page.getByLabel("Main rules");
  await expect(page.getByText("Default rules")).toBeVisible();
  await expect(rules).toHaveValue(/You are the receptionist of \{clinic_name\}/);

  await rules.fill("You are the receptionist of {clinic_name}. Be brief.");
  await expect(page.getByText("Edited", { exact: true })).toBeVisible();
  await expect(page.getByText("8 of 500 words")).toBeVisible();
  await expect(page.getByText(/Edited rules are only tested by your own calls/)).toBeVisible();
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText(/from the next call/)).toBeVisible();
  await page.reload();
  await expect(rules).toHaveValue("You are the receptionist of {clinic_name}. Be brief.");

  await page.getByRole("button", { name: "Reset to default" }).click();
  await expect(page.getByText("Default rules")).toBeVisible();
  await page.getByRole("button", { name: "Save" }).click();
  await page.reload();
  await expect(rules).toHaveValue(/what she may do|You are the receptionist of \{clinic_name\}, a clinic in India/);
  await expect(page.getByText("Default rules")).toBeVisible();
});

test("rules over 500 words can't be saved", async ({ page }) => {
  await page.goto("/admin/receptionist");
  await page.getByLabel("Main rules").fill("word ".repeat(501));
  await expect(page.getByRole("button", { name: "Rules over 500 words" })).toBeDisabled();
  await page.getByRole("button", { name: "Discard changes" }).click();
  await expect(page.getByText("Default rules")).toBeVisible();
});

test("the greeting switch and a timing are changed and put back", async ({ page }) => {
  await page.goto("/admin/receptionist");
  const greeting = page.getByRole("switch", { name: "Callers can talk over the greeting" });
  await expect(greeting).not.toBeChecked();
  await greeting.click();
  await page.getByLabel("End-of-turn wait (seconds)").fill("0.4");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText(/from the next call/)).toBeVisible();
  await page.reload();
  await expect(greeting).toBeChecked();
  await expect(page.getByLabel("End-of-turn wait (seconds)")).toHaveValue("0.4");
  await greeting.click();
  await page.getByLabel("End-of-turn wait (seconds)").fill("0.2");
  await page.getByRole("button", { name: "Save" }).click();
  await page.reload();
  await expect(greeting).not.toBeChecked();
});
