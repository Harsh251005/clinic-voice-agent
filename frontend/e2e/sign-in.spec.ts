// The signed-out pages and signing out. The e2e API runs with sign-in off,
// so these tests answer /api/me in the browser to be signed out, a viewer
// without a clinic, or a Google-signed-in admin. /api/auth/logout is answered
// here too: nothing reaches Google.
import { expect, test, type Page } from "@playwright/test";

const SIGNED_IN = {
  email: "staff@example.com",
  clinics: [{ id: 1, name: "Demo clinic", slug: "demo", staff: true }],
  is_admin: true,
  login: "google",
};

// Next adds its own (empty) role="alert" route announcer outside <main>: look inside main.
async function viewer(page: Page, me: object | "signed-out" | "offline") {
  await page.route("**/api/me", (route) =>
    me === "offline" ? route.abort()
      : me === "signed-out" ? route.fulfill({ status: 401, json: { detail: "Sign in first." } })
        : route.fulfill({ json: me }));
}

test("signed out: the sign-in card, the Google button, and no theme switch", async ({ page }) => {
  await viewer(page, "signed-out");
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Continue with Google" })).toHaveAttribute("href", "/api/auth/login");
  await expect(page.getByText("Access is by invitation.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Appearance" })).toHaveCount(0);
  await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
});

test("the Google button locks once clicked, so a second click does nothing", async ({ page }) => {
  await viewer(page, "signed-out");
  // 204: the browser stays on the page, as if Google were still loading.
  await page.route("**/api/auth/login", (route) => route.fulfill({ status: 204 }));
  await page.goto("/");
  await page.getByRole("link", { name: "Continue with Google" }).click({ noWaitAfter: true });
  const leaving = page.getByRole("link", { name: "Taking you to Google…" });
  await expect(leaving).toHaveAttribute("aria-disabled", "true");
});

test("each sign-in problem from the API is explained, unknown ones are not", async ({ page }) => {
  await viewer(page, "signed-out");
  await page.goto("/?signin=unverified");
  await expect(page.getByRole("main").getByRole("alert")).toContainText("That account can't be used");
  await page.goto("/?signin=failed");
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Sign-in didn't finish");
  await page.goto("/?signin=nonsense");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
});

test("the example call plays, in the real booking order, and starts over", async ({ page }) => {
  test.setTimeout(60_000);
  await viewer(page, "signed-out");
  await page.goto("/");
  const call = page.getByText("Patient call").locator("xpath=ancestor::div[contains(@class,'rounded-2xl')][1]");
  // Read-back before booking: name, number, then "Sab sahi hai na?", then booked.
  await expect(call.getByText("Patient ka naam aur das ank ka mobile number")).toBeVisible({ timeout: 20_000 });
  await expect(call.getByText("Sab sahi hai na?")).toBeVisible({ timeout: 20_000 });
  await expect(call.getByText("Appointment booked")).toBeVisible({ timeout: 20_000 });
  await expect(call.getByText("Appointment booked")).toBeHidden({ timeout: 10_000 }); // the loop restarts
  await expect(call.getByText(/^Namaste ji/)).toBeVisible({ timeout: 5_000 });
});

test("less motion asked for: the finished call, still", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await viewer(page, "signed-out");
  await page.goto("/");
  await expect(page.getByText("Appointment booked")).toBeVisible();
  await expect(page.getByText("Sab sahi hai na?")).toBeVisible();
});

test("the full-page messages use the same signed-out look", async ({ page }) => {
  await viewer(page, { ...SIGNED_IN, clinics: [], is_admin: false });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "No clinic yet" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign out and use another account" })).toBeVisible();

  await page.unrouteAll();
  await viewer(page, { ...SIGNED_IN, is_admin: false });
  await page.goto("/clinics/999/today");
  await expect(page.getByRole("heading", { name: "Clinic not found" })).toBeVisible();
  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: "Admins only" })).toBeVisible();

  await page.unrouteAll();
  await viewer(page, "offline");
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Can't connect" })).toBeVisible();
});

for (const [where, url, width] of [["clinic sidebar", "/clinics/1/setup", 1280], ["phone top bar", "/clinics/1/setup", 390], ["admin panel", "/admin", 1280]] as const) {
  test(`signing out asks first (${where}): stay, then sign out`, async ({ page }) => {
    await page.setViewportSize({ width, height: 800 });
    let logouts = 0;
    await viewer(page, SIGNED_IN);
    await page.route("**/api/auth/logout", (route) => { logouts++; return route.fulfill({ status: 204 }); });
    await page.goto(url);
    const account = page.getByRole("button", { name: "Account: staff@example.com" }).locator("visible=true");

    await account.click();
    await page.getByRole("menuitem", { name: "Sign out" }).click();
    const dialog = page.getByRole("alertdialog", { name: "Sign out of ClinicDesk?" });
    await expect(dialog).toContainText("staff@example.com");
    await dialog.getByRole("button", { name: "Stay signed in" }).click();
    await expect(dialog).toBeHidden();
    expect(logouts).toBe(0);

    await account.click(); // the page still answers clicks after the dialog
    await page.getByRole("menuitem", { name: "Sign out" }).click();
    await dialog.getByRole("button", { name: "Sign out" }).click();
    await expect(page).toHaveURL("/");
    expect(logouts).toBe(1);
  });
}
