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

test("a clinic's own receptionist settings are changed and put back", async ({ page }) => {
  // Admins only (sign-in is off here: the viewer is an admin).
  await page.goto("/clinics/1/setup?tab=receptionist");
  await expect(page.getByRole("tab", { name: "Receptionist", exact: true })).toBeVisible();
  const directions = page.getByLabel("How to find the clinic");
  const instructions = page.getByLabel("Instructions");
  await directions.fill("Opposite Borivali East station, first floor.");
  await instructions.fill("Tell callers parking is free.");
  await expect(page.getByText("5 of 150 words")).toBeVisible();
  await page.getByLabel("Speed").fill("0.95");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText(/from the next call/)).toBeVisible();
  await page.reload();
  await expect(directions).toHaveValue("Opposite Borivali East station, first floor.");
  await expect(page.getByLabel("Speed")).toHaveValue("0.95");

  await directions.fill("");
  await instructions.fill("");
  await page.getByLabel("Speed").fill("1");
  await page.getByRole("button", { name: "Save" }).click();
  await page.reload();
  await expect(directions).toHaveValue("");
  await expect(page.getByLabel("Speed")).toHaveValue("1");
});

test("instructions over 150 words can't be saved", async ({ page }) => {
  await page.goto("/clinics/1/setup?tab=receptionist");
  await page.getByLabel("Instructions").fill("word ".repeat(151));
  await expect(page.getByRole("button", { name: "Instructions over 150 words" })).toBeDisabled();
});
