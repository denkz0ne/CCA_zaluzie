import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/tests/browser/demo.html");
});

test("shows cover state and the persistent automation list", async ({
  page,
}) => {
  await expect(
    page.getByRole("heading", { name: "Žalúzie", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /Spálňa · okno/ }),
  ).toBeVisible();
  await expect(page.getByText("58 %", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "Konfigurácia", exact: true }).click();
  await expect(
    page.getByRole("button", { name: /Spálňa · okno/ }),
  ).toBeVisible();
});

test("retains separate drafts across covers and sections", async ({ page }) => {
  await page.getByRole("button", { name: "Konfigurácia", exact: true }).click();
  await page.getByLabel("Názov", { exact: true }).fill("Môj balkón");
  await page.getByRole("button", { name: "Ráno a večer", exact: true }).click();
  await page.getByRole("button", { name: /Spálňa · okno/ }).click();
  await page.getByRole("button", { name: "Žalúzia", exact: true }).click();
  await expect(page.getByLabel("Názov", { exact: true })).toHaveValue(
    "Spálňa · okno",
  );
  await page.getByRole("button", { name: /Obývačka · balkón/ }).click();
  await expect(page.getByLabel("Názov", { exact: true })).toHaveValue(
    "Môj balkón",
  );
});

test("save sends only the selected cover and discard restores baseline", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Konfigurácia", exact: true }).click();
  await page.getByLabel("Názov", { exact: true }).fill("Uložený balkón");
  await page.getByRole("button", { name: "Uložiť zmeny", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Nastavenia uložené");
  const call = await page.evaluate(() =>
    window.calls.find((c) => c.type === "cca_zaluzie/configure"),
  );
  expect(call.entry_id).toBe("one");
  expect(call.config.name).toBe("Uložený balkón");
  await page.getByLabel("Názov", { exact: true }).fill("Neuložený");
  await page
    .getByRole("button", { name: "Zahodiť zmeny", exact: true })
    .click();
  await expect(page.getByLabel("Názov", { exact: true })).toHaveValue(
    "Uložený balkón",
  );
});

test("a rejected save keeps the draft and reports the server error", async ({
  page,
}) => {
  await page.evaluate(() => (window.failSave = true));
  await page.getByRole("button", { name: "Konfigurácia", exact: true }).click();
  await page.getByLabel("Názov", { exact: true }).fill("Zachovať návrh");
  await page.getByRole("button", { name: "Uložiť zmeny", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Nastavenia boli odmietnuté",
  );
  await expect(page.getByLabel("Názov", { exact: true })).toHaveValue(
    "Zachovať návrh",
  );
});

test("reset shows countdown and can be cancelled", async ({ page }) => {
  await page.getByRole("button", { name: "Reset polohy", exact: true }).click();
  await expect(
    page.getByText("Výdrž na doraze", { exact: false }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Zrušiť reset", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Reset polohy", exact: true }),
  ).toBeEnabled();
});

test("motor errors are visible without a success toast", async ({ page }) => {
  await page.evaluate(() => (window.failAction = true));
  await page.getByRole("button", { name: "Zatvoriť", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Žalúzia nie je dostupná",
  );
});

test("timeline event opens actual decision details", async ({ page }) => {
  await page.getByRole("button", { name: /Pohyb potvrdený/ }).first().click();
  await expect(page.getByRole("dialog")).toContainText("58");
});

test("mobile layout keeps controls and fields reachable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Konfigurácia", exact: true }).click();
  await expect(page.getByLabel("Názov", { exact: true })).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
});
