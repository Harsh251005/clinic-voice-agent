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

test("the sign-in page says what ClinicDesk does, in four tiles, each once", async ({ page }) => {
  await viewer(page, "signed-out");
  await page.goto("/");
  const tiles = page.getByRole("region", { name: "What ClinicDesk does" }).getByRole("listitem");
  await expect(tiles).toHaveCount(4);
  for (const title of ["Books, moves, cancels", "Answers questions", "Keeps your diary", "Every call on record"]) {
    await expect(page.getByRole("heading", { name: title })).toHaveCount(1);
  }
  await expect(page.getByText("Patient call")).toHaveCount(0); // the old example call is gone
  // The light passes over one tile at a time, in reading order: four different start points.
  const delays = await tiles.evaluateAll((els) => els.map((el) => getComputedStyle(el).animationDelay));
  expect(delays).toEqual(["0s", "-7.5s", "-5s", "-2.5s"]);
});

test("less motion asked for: the tiles stay still", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await viewer(page, "signed-out");
  await page.goto("/");
  const tile = page.getByRole("region", { name: "What ClinicDesk does" }).getByRole("listitem").first();
  await expect(tile).toBeVisible();
  expect(await tile.evaluate((el) => getComputedStyle(el).animationName)).toBe("none");
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
