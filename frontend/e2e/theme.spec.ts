// Appearance: Light, Dark or the computer's own setting, kept in this browser.
import { expect, test } from "@playwright/test";

test("the appearance switch sets light or dark, and it sticks across a reload", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/clinics/1/today");
  const html = page.locator("html");
  await expect(html).toHaveAttribute("data-theme", "light"); // the computer's setting, by default

  await page.getByRole("button", { name: "Appearance" }).first().click();
  await page.getByRole("menuitemradio", { name: "Dark" }).click();
  await expect(html).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(html).toHaveAttribute("data-theme", "dark"); // set before the page paints, no flash

  await page.getByRole("button", { name: "Appearance" }).first().click();
  await page.getByRole("menuitemradio", { name: "Same as this computer" }).click();
  await expect(html).toHaveAttribute("data-theme", "light");
  await page.emulateMedia({ colorScheme: "dark" }); // the computer switches
  await expect(html).toHaveAttribute("data-theme", "dark");
});
