// Admin > Try: an admin chats with a clinic's receptionist. The brain is
// scripted (backend/tests/e2e_api.py); the session, the tools, the booking
// and the record are real.
import { expect, test } from "@playwright/test";

test("an admin chats, watches the tools work, sees what it did and erases it", async ({ page }) => {
  await page.goto("/admin");
  await page.getByRole("link", { name: "Try" }).first().click();
  await expect(page.getByRole("heading", { name: "Try the receptionist" })).toBeVisible();
  await page.getByRole("combobox", { name: "Clinic" }).click(); // other tests may have added clinics: pick ours
  await page.getByRole("option", { name: "Demo Family Clinic" }).click();
  await expect(page.getByText("Only her brain is paid for.")).toBeVisible();

  await page.getByRole("button", { name: "Start chat" }).click();
  await expect(page.getByText("Your turn")).toBeVisible();
  await expect(page.getByText(/Demo Family Clinic/).last()).toBeVisible(); // she greets first
  await expect(page.getByRole("combobox", { name: "Clinic" })).toBeDisabled(); // a chat keeps its clinic

  const box = page.getByLabel("What the caller says");
  await box.fill("कल पाँच बजे डॉक्टर आशा, नाम रवि");
  await box.press("Enter");
  await expect(page.getByText("कल पाँच बजे डॉक्टर आशा, नाम रवि")).toBeVisible();
  await expect(page.getByText("check_booking", { exact: true })).toBeVisible();
  await expect(page.getByText(/"patient_name": "Ravi"/)).toBeVisible(); // what she sent, unfolded
  await expect(page.getByText(/सही है\?/)).toBeVisible();

  await page.getByRole("switch", { name: "Tool details" }).click();
  await expect(page.getByText(/"patient_name": "Ravi"/)).toBeHidden();
  await page.getByRole("switch", { name: "Tool details" }).click();

  await expect(page.getByText("Your turn")).toBeVisible();
  await box.fill("हाँ, सही है");
  await box.press("Enter");
  await expect(page.getByText("book_appointment", { exact: true })).toBeVisible();
  await expect(page.getByText(/बुक हो गया/)).toBeVisible();

  await expect(page.getByText("Your turn")).toBeVisible();
  await box.fill("बस, धन्यवाद");
  await box.press("Enter");
  await expect(page.getByText("She said goodbye and hung up.")).toBeVisible();
  await expect(page.getByText("धन्यवाद, नमस्ते।", { exact: true })).toBeVisible();
  await expect(box).toHaveCount(0);

  await expect(page.getByRole("heading", { name: "What this chat did" })).toBeVisible();
  await expect(page.getByText(/Appointment #\d+ booked/)).toBeVisible();
  const booked = await page.request.get("/api/clinics/1/appointments/search?q=Ravi");
  expect(await booked.json()).toHaveLength(1);

  await page.getByRole("button", { name: "Erase this chat" }).click();
  await page.getByRole("button", { name: "Yes, erase it" }).click();
  await expect(page.getByText("Erased. Everything it booked, moved or cancelled is undone.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Start chat" })).toBeVisible();
  expect(await (await page.request.get("/api/clinics/1/appointments/search?q=Ravi")).json()).toEqual([]);
});

test("ending a chat yourself, and the link from a clinic's page", async ({ page }) => {
  await page.goto("/admin/clinics/1");
  await page.getByRole("link", { name: "Try her" }).click();
  await expect(page).toHaveURL(/\/admin\/try\?clinic=1$/);
  await page.getByRole("button", { name: "Start chat" }).click();
  await expect(page.getByText("Your turn")).toBeVisible();
  await page.getByRole("button", { name: "End chat" }).click();
  await expect(page.getByText("You ended the chat.")).toBeVisible();
  await expect(page.getByText("Nothing booked, moved or cancelled")).toBeVisible();
  await page.getByRole("button", { name: "Erase this chat" }).click();
  await page.getByRole("button", { name: "Yes, erase it" }).click();
  await expect(page.getByRole("button", { name: "Start chat" })).toBeVisible();
});
