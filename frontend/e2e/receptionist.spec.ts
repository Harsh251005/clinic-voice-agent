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
  const speed = page.getByRole("slider", { name: "Speed" });
  await speed.focus();
  await speed.press("ArrowLeft"); // one step slower: 1.00 to 0.95
  await expect(page.getByText("0.95×, normal")).toBeVisible();
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText(/from the next call/)).toBeVisible();
  await page.reload();
  await expect(directions).toHaveValue("Opposite Borivali East station, first floor.");
  await expect(speed).toHaveValue("0.95");

  await directions.fill("");
  await instructions.fill("");
  await speed.focus();
  await speed.press("ArrowRight");
  await page.getByRole("button", { name: "Save" }).click();
  await page.reload();
  await expect(directions).toHaveValue("");
  await expect(speed).toHaveValue("1");
});

test("a clinic's voice is picked from lists, and pitch shows only where the model has it", async ({ page }) => {
  // Harsh, 2026-11-12: dropdowns of women's voices, nothing typed.
  await page.goto("/clinics/1/setup?tab=receptionist");
  const model = page.getByRole("combobox", { name: "Voice model" });
  const voice = page.getByRole("combobox", { name: "Voice", exact: true });
  await expect(model).toHaveText("Bulbul v3");
  await expect(voice).toHaveText("Suhani");
  await expect(page.getByRole("slider", { name: "Pitch" })).toHaveCount(0);

  await voice.click();
  await expect(page.getByRole("option", { name: "Rahul" })).toHaveCount(0); // women only
  await page.getByRole("option", { name: "Priya" }).click();
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText(/from the next call/)).toBeVisible();
  await page.reload();
  await expect(voice).toHaveText("Priya");

  // The other model: she stays the same woman where it has her, and pitch appears.
  await model.click();
  await page.getByRole("option", { name: "Bulbul v4 flash" }).click();
  await expect(voice).toHaveText(/^Priya, /);
  const pitch = page.getByRole("slider", { name: "Pitch" });
  await expect(pitch).toBeVisible();
  await expect(page.getByText("Her own")).toBeVisible();

  // Back again: the pitch setting goes, and the clinic is left as it was.
  await model.click();
  await page.getByRole("option", { name: "Bulbul v3" }).click();
  await expect(pitch).toHaveCount(0);
  await voice.click();
  await page.getByRole("option", { name: "Suhani" }).click();
  await page.getByRole("button", { name: "Save" }).click();
  await page.reload();
  await expect(voice).toHaveText("Suhani");
});

test("instructions over 150 words can't be saved", async ({ page }) => {
  await page.goto("/clinics/1/setup?tab=receptionist");
  await page.getByLabel("Instructions").fill("word ".repeat(151));
  await expect(page.getByRole("button", { name: "Instructions over 150 words" })).toBeDisabled();
});
