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
