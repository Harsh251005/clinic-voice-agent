// Costs against the real API: the seeded calls' usage (e2e/start-api.sh)
// priced in rupees with the seeded official prices, and a price changed in
// the panel re-pricing them at once, no code involved.
import { expect, test } from "@playwright/test";

test.describe.configure({ mode: "serial" }); // the second test changes a price the first reads

test("the month and each call cost in rupees", async ({ page }) => {
  await page.goto("/admin/costs");
  await expect(page.getByRole("heading", { name: "Costs" })).toBeVisible();
  // Two calls, each: 41 s heard (₹0.34), 9,200 + 380 tokens (₹0.16), 610 characters (₹1.83).
  await expect(page.getByText("You pay this month")).toBeVisible();
  await expect(page.getByText("₹4.66").first()).toBeVisible();
  await page.getByRole("link", { name: /Demo Family Clinic.*₹2\.33/ }).first().click();
  const cost = page.getByRole("region", { name: "What this call cost" });
  await expect(cost.getByText("₹2.33")).toBeVisible();
  await expect(cost.getByText("at ₹30 per hour heard")).toBeVisible();
  await expect(cost.getByText("at ₹30 per 10,000 characters spoken")).toBeVisible();
});

test("a price changed in the panel re-prices the calls", async ({ page }) => {
  await page.goto("/admin/costs/prices");
  const speaking = page.getByRole("listitem").filter({ hasText: "per 10,000 characters spoken" });
  await speaking.getByRole("button", { name: "Change" }).click();
  const form = page.getByRole("dialog");
  await form.getByLabel("Price", { exact: true }).fill("60");
  await form.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Saved.")).toBeVisible();
  await expect(speaking.getByText("₹60.00 per 10,000 characters spoken")).toBeVisible();
  await page.goto("/admin/costs");
  await expect(page.getByText("₹8.32").first()).toBeVisible(); // speaking doubled: ₹3.66 more
});

test("a language model is one price row: input, cached and output, changed together", async ({ page }) => {
  await page.goto("/admin/costs/prices");
  const prices = page.getByRole("region", { name: "Vendor prices" });
  const model = prices.getByRole("listitem").filter({ hasText: "sarvam-105b-conversations" });
  await expect(model).toHaveCount(1);
  await expect(model).toContainText("Input ₹15.00 · Cached input ₹5.00 · Output ₹60.00 per million tokens");
  await expect(page.getByText(/ElevenLabs|eleven_|scribe_/)).toHaveCount(0); // Hindi first: not on this page

  await model.getByRole("button", { name: "Change" }).click();
  const form = page.getByRole("dialog");
  await expect(form.getByLabel("Charged for")).toHaveCount(0); // a model stays a model
  await form.getByLabel("Output per 1M tokens").fill("120");
  await form.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Saved.")).toBeVisible();
  await expect(model).toContainText("Input ₹15.00 · Cached input ₹5.00 · Output ₹120.00 per million tokens");
  await expect(prices.getByRole("listitem").filter({ hasText: "sarvam-105b-conversations" })).toHaveCount(1);
  await page.goto("/admin/costs");
  await expect(page.getByText("₹8.37").first()).toBeVisible(); // 380 output tokens a call, now twice the price
});

test("adding a language model asks for its three prices at once", async ({ page }) => {
  await page.goto("/admin/costs/prices");
  await page.getByRole("button", { name: "Add a price" }).click();
  const form = page.getByRole("dialog");
  await expect(form.getByLabel("Charged for")).toContainText("Language model");
  await form.getByLabel("Model").fill("sarvam-m");
  await form.getByLabel("Input per 1M tokens").fill("10");
  await form.getByLabel("Cached per 1M tokens").fill("2");
  await form.getByLabel("Output per 1M tokens").fill("40");
  await expect(form.getByLabel("For how many")).toHaveCount(0);
  await form.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Added.")).toBeVisible();
  const model = page.getByRole("listitem").filter({ hasText: "sarvam-m" }).filter({ hasNotText: "105b" });
  await expect(model).toContainText("Input ₹10.00 · Cached input ₹2.00 · Output ₹40.00 per million tokens");
  await model.getByRole("button", { name: "Remove" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Remove" }).click();
  await expect(page.getByText("Removed.")).toBeVisible();
  await expect(model).toHaveCount(0);
});
