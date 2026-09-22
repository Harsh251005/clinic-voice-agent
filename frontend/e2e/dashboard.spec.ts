// The dashboard's main flows, clicked through against the real API and a
// fresh database (e2e/start-api.sh: the demo clinic plus one booking today).
// Tests share that database and run in order.
import { expect, test, type Page } from "@playwright/test";

const SETUP = "/clinics/1/setup";

async function pick(page: Page, label: string, option: string) {
  await page.getByRole("combobox", { name: label }).click();
  await page.getByRole("option", { name: option, exact: true }).click();
}

test("home opens the clinic's appointments for today", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/clinics\/1\/appointments/);
  await expect(page.getByRole("heading", { name: "Appointments" })).toBeVisible();
  await expect(page.getByText("Riya Sharma")).toBeVisible();
  await expect(page.getByText("98200 12345")).toBeVisible();
  await expect(page.getByText("Sign-in is off")).toBeVisible();
});

test("moving between days keeps the day in the URL", async ({ page }) => {
  await page.goto("/clinics/1/appointments");
  await page.getByRole("button", { name: "Next day" }).click();
  await expect(page).toHaveURL(/day=\d{4}-\d{2}-\d{2}/);
  await expect(page.getByText(/No appointments on/)).toBeVisible();
  await page.getByRole("button", { name: "Today" }).click();
  await expect(page.getByText("Riya Sharma")).toBeVisible();
});

test("cancelling asks first, then frees the slot", async ({ page }) => {
  await page.goto("/clinics/1/appointments");
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(page.getByRole("alertdialog")).toContainText("Cancel Riya Sharma's appointment?");
  await page.getByRole("button", { name: "Yes, cancel" }).click();
  await expect(page.getByText(/Cancelled Riya Sharma's .* appointment/)).toBeVisible();
  await expect(page.getByText(/No appointments on/)).toBeVisible();
  await page.getByText("Show cancelled").click();
  await expect(page.getByText("Cancelled", { exact: true })).toBeVisible();
});

test("staff book a walk-in, then change it", async ({ page }) => {
  await page.goto("/clinics/1/appointments");
  await page.getByRole("button", { name: "New appointment" }).click();
  await expect(page.getByRole("dialog")).toContainText("New appointment");
  await page.getByLabel("Patient name").fill("Meena Joshi");
  await page.getByLabel("Mobile number").fill("98190 22222");
  await page.getByLabel("Reason for visit (optional)").fill("Tooth pain since Monday");
  await page.getByLabel("Time", { exact: true }).fill("11:05");  // off the grid: a walk-in
  await page.getByRole("button", { name: "Book appointment" }).click();
  await expect(page.getByText(/^Booked: Meena Joshi with Dr. Asha Mehta/)).toBeVisible();
  await expect(page.getByText("Tooth pain since Monday")).toBeVisible();
  await expect(page.getByText("Staff", { exact: true })).toBeVisible();

  const row = page.locator("div").filter({ hasText: /^11:05 am/ }).first();
  await row.getByRole("button", { name: "Edit" }).click();
  await page.getByLabel("Patient name").fill("Meena R Joshi");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText(/^Saved: Meena R Joshi/)).toBeVisible();
  await expect(page.getByText("Meena R Joshi")).toBeVisible();
});

test("a double booking is refused with a reason", async ({ page }) => {
  await page.goto("/clinics/1/appointments");
  await page.getByRole("button", { name: "New appointment" }).click();
  await page.getByLabel("Patient name").fill("Someone Else");
  await page.getByLabel("Mobile number").fill("9819033333");
  await page.getByLabel("Time", { exact: true }).fill("11:05");
  await page.getByRole("button", { name: "Book appointment" }).click();
  await expect(page.getByText(/already has .* from 11:05 to 11:20/)).toBeVisible();
});

test("a new doctor starts with the common week", async ({ page }) => {
  await page.goto(`${SETUP}?tab=doctors`);
  await page.getByLabel("Name", { exact: true }).fill("Dr. Neha Kulkarni");
  await expect(page.getByRole("combobox", { name: "Starting hours" })).toHaveText("Mon–Sat, 10 am–1 pm and 5–8 pm");
  await page.getByRole("button", { name: "Add doctor" }).click();
  await expect(page.getByText(/Dr. Neha Kulkarni added with Mon–Sat/)).toBeVisible();
  // Exact name: the add form's hidden option list also mentions "Same as Dr. Neha Kulkarni".
  const card = page.locator('[data-slot="card"]').filter({ has: page.getByText("Dr. Neha Kulkarni", { exact: true }) });
  await expect(card).toContainText("Monday to Saturday 10:00-13:00 and 17:00-20:00; Sunday not available");
});

test("a doctor can be removed for good, after a warning", async ({ page }) => {
  await page.goto(`${SETUP}?tab=doctors`);
  await page.getByLabel("Name", { exact: true }).fill("Dr. Temp Locum");
  await page.getByRole("button", { name: "Add doctor" }).click();
  const card = page.locator('[data-slot="card"]').filter({ has: page.getByText("Dr. Temp Locum", { exact: true }) });
  await card.getByRole("button", { name: "Remove" }).click();
  await expect(page.getByRole("alertdialog")).toContainText("Remove Dr. Temp Locum for good?");
  await page.getByRole("button", { name: "Yes, remove" }).click();
  await expect(page.getByText("Dr. Temp Locum removed")).toBeVisible();
  await expect(card).toBeHidden();
});

test("weekly hours: apply a pattern, see it described, save", async ({ page }) => {
  await page.goto(`${SETUP}?tab=hours`);
  await pick(page, "Doctor", "Dr. Rohan Iyer");
  await pick(page, "Pattern", "Mon–Fri, 9 am–5 pm");
  await page.getByRole("button", { name: "Apply" }).click();
  await expect(page.getByText("Unsaved changes")).toBeVisible();
  await expect(page.getByText("Monday to Friday 09:00-17:00; Saturday to Sunday not available")).toBeVisible();
  await page.getByRole("button", { name: "Save hours" }).click();
  await expect(page.getByText("Hours saved for Dr. Rohan Iyer")).toBeVisible();
  await expect(page.getByText("Unsaved changes")).toBeHidden();
});

test("weekly hours: overlapping sittings are explained and can't be saved", async ({ page }) => {
  await page.goto(`${SETUP}?tab=hours`);
  await pick(page, "Doctor", "Dr. Asha Mehta");
  await page.getByLabel("Tuesday second from").fill("12:00");
  await expect(page.getByText("Tuesday: the second sitting starts before the first one ends.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Save hours" })).toBeDisabled();
  await page.getByRole("button", { name: "Discard changes" }).click();
  await expect(page.getByText("Unsaved changes")).toBeHidden();
});

test("weekly hours: copy Monday to the other open days", async ({ page }) => {
  await page.goto(`${SETUP}?tab=hours`);
  await pick(page, "Doctor", "Dr. Asha Mehta");
  await page.getByLabel("Monday from", { exact: true }).fill("09:00");
  await page.getByRole("button", { name: "Copy Monday to all open days" }).click();
  await expect(page.getByLabel("Saturday from", { exact: true })).toHaveValue("09:00");
  await expect(page.getByLabel("Sunday from", { exact: true })).toBeDisabled(); // closed days stay closed
});

test("FAQ answers can be added and removed", async ({ page }) => {
  await page.goto(`${SETUP}?tab=faq`);
  await page.getByLabel("Question").fill("Do you do home visits?");
  await page.getByLabel("Answer").fill("No, only at the clinic.");
  await page.getByRole("button", { name: "Add answer" }).click();
  await expect(page.getByText("Do you do home visits?")).toBeVisible();
  await page.getByRole("button", { name: 'Remove "Do you do home visits?"' }).click();
  await expect(page.getByText("Do you do home visits?")).toBeHidden();
});

test("a clinic holiday can be added", async ({ page }) => {
  await page.goto(`${SETUP}?tab=time-off`);
  await expect(page.getByText("Nothing planned.")).toBeVisible();
  await page.getByLabel("Reason (optional)").fill("Diwali");
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await expect(page.getByText("Diwali")).toBeVisible();
  await expect(page.getByText("Whole clinic", { exact: true })).toBeVisible();
});

test("a bad link name is explained, not saved", async ({ page }) => {
  await page.goto(`${SETUP}?tab=link`);
  // A textbox: the tab panel is also named "Call link", after its tab.
  await expect(page.getByRole("textbox", { name: "Call link" })).toHaveValue(/\/call\/demo-family-clinic$/);
  await page.getByLabel("Link name").fill("bad name");
  await page.getByRole("button", { name: "Save link name" }).click();
  await expect(page.getByText(/3-60 characters/)).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Link name")).toHaveValue("demo-family-clinic");
});

test("an admin creates a clinic and lands on its doctors", async ({ page }) => {
  await page.goto("/new-clinic");
  await page.getByLabel("Clinic name").fill("Sharma Skin Clinic");
  await page.getByRole("button", { name: "Create clinic" }).click();
  await expect(page).toHaveURL(/\/clinics\/\d+\/setup\?tab=doctors/);
  await expect(page.getByRole("heading", { name: "Sharma Skin Clinic" })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Clinic" })).toHaveText("Sharma Skin Clinic");
});
