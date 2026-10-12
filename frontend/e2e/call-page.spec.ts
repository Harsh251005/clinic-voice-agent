import { expect, test } from "@playwright/test";

// The patient's call page (served by the API): the caller picks the call's
// language, which stays the same for the whole call.
const PAGE = "http://127.0.0.1:8095/call/demo-family-clinic";

test("the caller picks the call's language and the page remembers it", async ({ page }) => {
  // Answer the pass request here: no LiveKit room, and a "too many calls"
  // reply is a limit working, so the page reports no problem.
  await page.route("**/call/demo-family-clinic/pass", (route) =>
    route.fulfill({ status: 429, json: { error: "Too many calls just now. Please wait a few minutes and try again." } }));
  await page.goto(PAGE);

  const hindi = page.getByRole("radio", { name: "हिन्दी" });
  const english = page.getByRole("radio", { name: "English" });
  await expect(hindi).toBeChecked(); // most callers' language, first time on this device
  await english.check();

  const pass = page.waitForRequest((r) => r.url().endsWith("/call/demo-family-clinic/pass"));
  await page.getByRole("button", { name: "Start the call" }).click();
  expect((await pass).postDataJSON()).toEqual({ language: "en" });
  await expect(page.getByText("Too many calls just now.")).toBeVisible();

  await page.reload();
  await expect(english).toBeChecked();
});
