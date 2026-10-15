import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/tests/browser/demo.html");
  await page.waitForFunction(
    () =>
      Array.isArray(window.fixture?.controllers) &&
      Array.isArray(window.calls) &&
      typeof window.publish === "function",
  );
});

test("history period is selectable", async ({ page }) => {
  await page.getByLabel("Obdobie histórie").selectOption("6");
  await expect(
    page.getByRole("heading", { name: "Priebeh za posledných 6 hodín" }),
  ).toBeVisible();
});

test("save locks edits until the response arrives", async ({ page }) => {
  await page.evaluate(() => {
    window.saveGate = new Promise((resolve) => (window.finishSave = resolve));
  });
  await page.getByRole("button", { name: "Konfigurácia", exact: true }).click();
  await page.getByLabel("Názov", { exact: true }).fill("Uložiť celý návrh");
  await page.getByRole("button", { name: "Uložiť zmeny", exact: true }).click();
  await expect(page.getByLabel("Názov", { exact: true })).toBeDisabled();
  await page.evaluate(() => window.finishSave());
  await expect(page.getByLabel("Názov", { exact: true })).toBeEnabled();
  await expect(page.getByLabel("Názov", { exact: true })).toHaveValue(
    "Uložiť celý návrh",
  );
});

test("removing the selected controller selects a remaining cover", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Konfigurácia", exact: true }).click();
  await page.evaluate(() => window.publish({ entry_id: "one" }));
  await expect(page.getByLabel("Názov", { exact: true })).toHaveValue(
    "Spálňa · okno",
  );
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
  await page
    .getByRole("button", { name: /Pohyb potvrdený/ })
    .first()
    .click();
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

test("hides position source for reliable automatic feedback", async ({
  page,
}) => {
  await page.evaluate(() => {
    const c = window.fixture.controllers[0];
    c.position_source = {
      automatic: true,
      selected: "current_position",
      reason: null,
    };
    window.publish({ controller: c });
  });
  await page.getByRole("button", { name: "Konfigurácia", exact: true }).click();
  await expect(page.getByLabel("Zdroj polohy", { exact: true })).toHaveCount(0);
});

test("unresolved feedback exposes reason and saves a manual source", async ({
  page,
}) => {
  await page.evaluate(() => {
    const c = window.fixture.controllers[0];
    c.position_source = {
      automatic: true,
      selected: null,
      reason: "ambiguous_position_feedback",
    };
    window.publish({ controller: c });
  });
  await page.getByRole("button", { name: "Konfigurácia", exact: true }).click();
  await expect(page.getByText(/dve rozdielne polohy/)).toBeVisible();
  await page
    .getByLabel("Zdroj polohy", { exact: true })
    .selectOption("position");
  await page.getByRole("button", { name: "Uložiť zmeny", exact: true }).click();
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          window.calls.findLast((call) => call.type === "cca_zaluzie/configure")
            ?.config?.position_source_auto,
      ),
    )
    .toBe(false);
  expect(
    await page.evaluate(
      () =>
        window.calls.findLast((call) => call.type === "cca_zaluzie/configure")
          .config.position_source,
    ),
  ).toBe("position");
});

test("add cover link starts the Home Assistant integration flow", async ({
  page,
}) => {
  await expect(
    page.getByRole("link", { name: "＋ Pridať žalúziu" }),
  ).toHaveAttribute(
    "href",
    "/config/integrations/dashboard/add?domain=cca_zaluzie",
  );
});

test("dry-run status is conspicuous and can be turned off per cover", async ({
  page,
}) => {
  await page.evaluate(() => {
    window.fixture.controllers[0].simulation = {
      enabled: true,
      shadow: { position: 42 },
    };
    window.fixture.controllers[0].events.push({
      id: "simulated-command",
      at: new Date().toISOString(),
      type: "would_dispatch",
      simulated: true,
      details: { target: 42 },
    });
    window.publish({ controller: window.fixture.controllers[0] });
  });
  await expect(
    page.getByText("SIMULÁCIA — motor je zablokovaný"),
  ).toBeVisible();
  await expect(page.getByText("Simulovaná poloha: 42 %")).toBeVisible();
  await page.getByLabel("Filtrovať simuláciu").selectOption("would_dispatch");
  await expect(
    page.getByText("Simulácia: motorový povel by sa odoslal"),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Vypnúť simuláciu", exact: true })
    .click();
  await expect
    .poll(() =>
      page.evaluate(() =>
        window.calls.some(
          (call) =>
            call.type === "cca_zaluzie/control" &&
            call.action === "simulation_off" &&
            call.entry_id === "one",
        ),
      ),
    )
    .toBe(true);
});

test("prediction can be requested for a selected future date and week", async ({
  page,
}) => {
  await page.getByLabel("Dátum predikcie").fill("2026-10-22");
  await page.getByLabel("Rozsah predikcie").selectOption("7");
  await expect
    .poll(() =>
      page.evaluate(() =>
        window.calls.some(
          (call) =>
            call.type === "cca_zaluzie/predict" &&
            call.start_date === "2026-10-22" &&
            call.days === 7,
        ),
      ),
    )
    .toBe(true);
  await expect(
    page.getByText("Predikcia je scenár podľa uložených pravidiel"),
  ).toBeVisible();
});
