import { test, expect } from "@playwright/test";

test("passage protection is an explicit header switch next to the single window contact", async ({
  page,
}) => {
  await page.goto("/tests/browser/demo.html");
  await page.waitForFunction(() => typeof window.publish === "function");
  await page.getByRole("button", { name: "Konfigurácia", exact: true }).click();
  await page.locator('[data-group="windows"]').click();
  const protection = page
    .locator(".settings-card")
    .filter({
      has: page.getByRole("heading", {
        name: "Ochrana priechodu",
        exact: true,
      }),
    });
  await expect(protection).toBeVisible();
  await expect(
    protection.locator('.feature-header [data-key="contact_lockout_enabled"]'),
  ).toBeVisible();
  await expect(protection).toContainText("30 minút");
  await expect(page.locator('[data-key="window_open"]')).toHaveCount(1);
  for (const key of [
    "window_tilted",
    "tilted_lockout",
    "tilted_blocks",
    "vent_keep_full_tilt",
    "vent_lower_from_above",
    "vent_after_shade",
  ])
    await expect(page.locator(`[data-key="${key}"]`)).toHaveCount(0);
  await page.locator('[data-key="ventilation_enabled"]').check();
  await protection.locator('[data-key="contact_lockout_enabled"]').uncheck();
  await page.locator("[data-save]").click();
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          window.calls.findLast((c) => c.type === "cca_zaluzie/configure")
            ?.config.contact_lockout_enabled,
      ),
    )
    .toBe(false);
});
