// Talk to receptionist: staff call their own receptionist; the call is real,
// so it can be erased afterwards with everything it did.
import { expect, test } from "@playwright/test";
import { testCallThatBooked } from "./backend";

test("staff can start a test call in either language, and see why it can't start", async ({ page }) => {
  // Answered here: the e2e API has no LiveKit, and this is the API's own refusal.
  await page.route("**/api/clinics/*/calls/test", (route) =>
    route.fulfill({ status: 409, json: { detail: "Calls in Hindi aren't available right now." } }));
  await page.goto("/");
  await page.waitForURL(/\/today$/);
  await page.getByRole("link", { name: "Talk to receptionist" }).first().click();
  await expect(page.getByRole("heading", { name: "Talk to your receptionist" })).toBeVisible();
  await expect(page.getByText("This is a real call.")).toBeVisible();
  await expect(page.getByRole("radio", { name: "हिन्दी" })).toHaveAttribute("aria-checked", "true");

  const asked = page.waitForRequest((r) => r.url().endsWith("/calls/test"));
  await page.getByRole("button", { name: "Start test call" }).click();
  expect((await asked).postDataJSON()).toEqual({ language: "hi" });
  await expect(page.getByText("Calls in Hindi aren't available right now.")).toBeVisible();
});

test("a test call is marked, and erasing it undoes its booking", async ({ page }) => {
  const callId = testCallThatBooked();
  await page.goto("/");
  await page.waitForURL(/\/today$/);
  const clinicUrl = page.url().replace(/\/today$/, "");
  await page.goto(`${clinicUrl}/calls`);
  await expect(page.getByText("Test", { exact: true }).first()).toBeVisible();

  await page.goto(`${clinicUrl}/calls/${callId}`);
  await expect(page.getByRole("heading", { name: /^Test call · / })).toBeVisible();
  await page.getByRole("button", { name: "Erase this test call" }).click();
  await expect(page.getByText("Every appointment it booked, moved or cancelled goes back to how it was")).toBeVisible();
  await page.getByRole("button", { name: "Yes, erase it" }).click();
  await expect(page.getByText("Test call erased. Everything it did is undone.")).toBeVisible();
  await expect(page).toHaveURL(`${clinicUrl}/calls`);

  const res = await page.request.get(`/api/clinics/${clinicUrl.split("/").pop()}/appointments/search?q=Test%20Patient`);
  expect(await res.json()).toEqual([]);
});
