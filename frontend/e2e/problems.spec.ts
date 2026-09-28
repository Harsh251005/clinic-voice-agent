// Problems flagged on every page: the e2e API runs with no agent worker, so
// the receptionist is offline until a heartbeat is written into the
// throwaway e2e database (never real data). Runs after the other specs.
import { expect, test, type Page } from "@playwright/test";
import { heartbeat } from "./backend";

const API = "http://127.0.0.1:8095";

/** The API re-checks problems every 30 s and the page every 30 s: reload until it shows. */
async function until(page: Page, check: () => Promise<boolean>) {
  await expect.poll(async () => {
    await page.reload();
    await page.waitForLoadState("networkidle");
    return check();
  }, { timeout: 75_000, intervals: [2_000, 5_000] }).toBe(true);
}

test.describe.configure({ timeout: 120_000 });

test("the receptionist being offline is flagged on every clinic page, and clears", async ({ page }) => {
  heartbeat(3600);  // earlier specs checked a worker in: that worker has now stopped
  const offline = page.getByRole("alert").filter({ hasText: "Your receptionist is offline" });
  await page.goto("/clinics/1/today");
  await until(page, async () => (await offline.count()) === 1);
  await expect(page.getByText("Offline. Patients can't reach it right now.")).toBeVisible();
  for (const where of ["appointments", "calls", "setup"]) {
    await page.goto(`/clinics/1/${where}`);
    await expect(offline).toBeVisible();
  }
  await expect(offline.getByRole("button", { name: "Seen" })).toHaveCount(0);  // urgent: can't be put away
  await expect(page).toHaveTitle(/^\(!\) /);
  await expect(page.getByRole("button", { name: "Problems: 1 open" }).first()).toBeVisible();

  heartbeat();
  await until(page, async () => (await offline.count()) === 0);
  await expect(page).not.toHaveTitle(/^\(!\) /);
  await page.getByRole("button", { name: "Problems: none open" }).first().click();
  await expect(page.getByRole("dialog")).toContainText("Fixed in the last 7 days");
});

test("a patient who couldn't get through is flagged to the clinic, who can mark it seen", async ({ page, request }) => {
  heartbeat();
  const r = await request.post(`${API}/call/demo-family-clinic/report`, { data: { reason: "mic_blocked" } });
  expect(r.status()).toBe(204);
  await page.goto("/clinics/1/today");
  const banner = page.getByRole("status").filter({ hasText: "1 patient couldn't reach your receptionist" });
  await expect(banner).toContainText("their browser blocked the microphone");
  await banner.getByRole("button", { name: "Seen" }).click();
  await expect(banner).toHaveCount(0);
  await page.getByRole("button", { name: "Problems: 1 open" }).first().click();  // still in the bell
  await expect(page.getByRole("dialog")).toContainText("couldn't reach your receptionist");
});

test("the operator sees the same problem technically, with the clinic named", async ({ page }) => {
  heartbeat();
  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: /Open problems/ })).toBeVisible();
  await expect(page.getByText("Demo Family Clinic: 1 patient couldn't connect (mic_blocked).").first()).toBeVisible();
  await page.goto("/admin/clinics");
  // Clinics added by the admin tests have no doctors yet: they carry a dot too, rightly.
  await expect(page.getByRole("link", { name: /^Needs attention: Demo Family Clinic/ })).toBeVisible();
});
