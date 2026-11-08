import { expect, test } from "@playwright/test";

// The patient's call page (served by the API): every call is in Hindi, so
// the page says so and asks for no choice.
const PAGE = "http://127.0.0.1:8095/call/demo-family-clinic";

test("the call page starts a Hindi call with no language to choose", async ({ page }) => {
  // Answer the pass request here: no LiveKit room, and a "too many calls"
  // reply is a limit working, so the page reports no problem.
  await page.route("**/call/demo-family-clinic/pass", (route) =>
    route.fulfill({ status: 429, json: { error: "Too many calls just now. Please wait a few minutes and try again." } }));
  await page.goto(PAGE);

  await expect(page.getByText("Call in Hindi")).toBeVisible();
  await expect(page.getByRole("radio")).toHaveCount(0);
  await expect(page.getByText("English", { exact: true })).toHaveCount(0);

  const pass = page.waitForRequest((r) => r.url().endsWith("/call/demo-family-clinic/pass"));
  await page.getByRole("button", { name: "Start the call" }).click();
  expect((await pass).postData()).toBeNull(); // nothing to choose, nothing sent
  await expect(page.getByText("Too many calls just now.")).toBeVisible();
});
