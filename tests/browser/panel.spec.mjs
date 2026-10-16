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

test("live snapshots patch the panel without replacing focused controls or dialogs", async ({
  page,
}) => {
  const root = page.locator("main.layout");
  await page.evaluate(() => {
    const shadow = document.querySelector("cca-zaluzie-panel").shadowRoot;
    window.rootBefore = shadow.querySelector("main.layout");
    window.rowBefore = shadow.querySelector('[data-row="one"]');
  });
  await page.locator('[data-cover="two"]').click();
  await page.getByRole("button", { name: "Konfigurácia", exact: true }).click();
  const name = page.locator('[data-key="name"]');
  await name.fill("Rozpracovaný názov");
  await page.evaluate(() => {
    window.inputBefore = document
      .querySelector("cca-zaluzie-panel")
      .shadowRoot.querySelector('[data-key="name"]');
    for (let i = 0; i < 20; i++) {
      const controller = structuredClone(window.fixture.controllers[1]);
      controller.position = i;
      window.publish({ controller });
    }
  });
  await expect(name).toHaveValue("Rozpracovaný názov");
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          document
            .querySelector("cca-zaluzie-panel")
            .shadowRoot.querySelector("main.layout") === window.rootBefore &&
          document
            .querySelector("cca-zaluzie-panel")
            .shadowRoot.querySelector('[data-key="name"]') ===
            window.inputBefore &&
          document.querySelector("cca-zaluzie-panel").shadowRoot
            .activeElement === window.inputBefore,
      ),
    )
    .toBe(true);

  await page.getByRole("button", { name: "Prehľad", exact: true }).click();
  await page.locator("[data-event]").first().click();
  await expect(page.locator("dialog")).toBeVisible();
  await page.evaluate(() => {
    const controller = structuredClone(window.fixture.controllers[1]);
    controller.position = 41;
    window.publish({ controller });
  });
  await expect(page.locator("dialog")).toBeVisible();
  await expect(root).toHaveCount(1);
});

test("server clock-only snapshots do not trigger a redundant panel render", async ({
  page,
}) => {
  await page.evaluate(() => {
    const panel = document.querySelector("cca-zaluzie-panel");
    panel.liveRenderCount = 0;
    const render = panel._render.bind(panel);
    panel._render = (...args) => {
      panel.liveRenderCount++;
      return render(...args);
    };
    const controller = structuredClone(panel._controllers.get("one"));
    controller.server_time += 10;
    window.publish({ controller });
  });
  await page.waitForTimeout(80);
  await expect
    .poll(() =>
      page.evaluate(
        () => document.querySelector("cca-zaluzie-panel").liveRenderCount,
      ),
    )
    .toBe(0);
});

test("live history updates add correctly namespaced SVG measurement points", async ({
  page,
}) => {
  await page.evaluate(() => {
    const controller = structuredClone(window.fixture.controllers[0]);
    const now = Date.now();
    controller.position_history = [
      { at: new Date(now - 1000).toISOString(), position: 35, available: true },
      { at: new Date(now).toISOString(), position: 42, available: true },
    ];
    window.publish({ controller });
  });
  await expect(page.locator('circle[data-point-position="42"]')).toHaveCount(1);
  await expect
    .poll(() =>
      page
        .locator("circle[data-measurement]")
        .evaluateAll((nodes) =>
          nodes.every(
            (node) => node.namespaceURI === "http://www.w3.org/2000/svg",
          ),
        ),
    )
    .toBe(true);
});

test("active motion is shown separately from confirmed position", async ({
  page,
}) => {
  await page.evaluate(() => {
    const controller = structuredClone(window.fixture.controllers[0]);
    controller.position = 58;
    controller.motion = {
      status: "opening",
      direction: "opening",
      target: 100,
      source: "cover_entity",
      simulated: false,
    };
    window.publish({ controller });
  });
  await expect(page.getByText("Otvára sa…").first()).toBeVisible();
  await expect(page.locator(".position-number")).toContainText("58");
  await expect(page.getByText("Cieľ počas pohybu: 100 %")).toBeVisible();
});

test("phase controls stay beside primary position controls and action keys are localized", async ({
  page,
}) => {
  await page.evaluate(() => {
    const controller = structuredClone(window.fixture.controllers[0]);
    controller.config.shading_enabled = true;
    controller.config.ventilation_enabled = true;
    controller.runtime.shading = false;
    controller.decision.mode = "idle";
    const panel = document.querySelector("cca-zaluzie-panel");
    panel._predictions.set(panel._selected, {
      events: [
        {
          type: "close",
          mode: "schedule",
          status: "computed",
          target: 0,
          scenario_at: new Date().toISOString(),
        },
      ],
    });
    window.publish({ controller });
    panel._render();
  });
  const controls = page.locator(".motor-controls");
  await expect(
    controls.getByRole("button", { name: "Začať tienenie teraz" }),
  ).toBeVisible();
  await expect(
    controls.getByRole("button", { name: "Začať vetranie" }),
  ).toBeVisible();
  await expect(page.getByText("Večerné zatvorenie").first()).toBeVisible();
  await expect(page.getByText(/^close$/)).toHaveCount(0);
});

test("cover list has a compact accessible drag grip without persistent selection row", async ({
  page,
}) => {
  await expect(page.locator(".drag-grip").first()).toHaveAttribute(
    "aria-label",
    /Presunúť/,
  );
  await expect(page.locator(".select-cover")).toHaveCount(0);
  await expect(page.locator(".order-buttons")).toHaveCount(0);
  await expect(
    page.getByText("Presunúť automatizáciu", { exact: true }),
  ).toHaveCount(0);
  await expect(page.locator("[data-cover]").first()).toBeVisible();
});

test("an old observed direction is not displayed as active motion", async ({
  page,
}) => {
  await page.evaluate(() => {
    const controller = structuredClone(window.fixture.controllers[0]);
    controller.last_movement = {
      direction: "closing",
      at: new Date().toISOString(),
    };
    controller.motion = { status: "idle", direction: null, target: null };
    window.publish({ controller });
  });
  await expect(page.locator('[data-direction="closing"]')).toHaveCount(0);
});

test("touch long press adds a second cover to the multi-selection", async ({
  page,
}) => {
  await page.locator('[data-cover="two"]').dispatchEvent("pointerdown", {
    pointerType: "touch",
    pointerId: 7,
    isPrimary: true,
    button: 0,
  });
  await page.waitForTimeout(600);
  await page.locator('[data-cover="two"]').dispatchEvent("pointerup", {
    pointerType: "touch",
    pointerId: 7,
    isPrimary: true,
    button: 0,
  });
  await expect(page.locator('[data-row="two"]')).toHaveClass(/multi-selected/);
  await page.getByRole("button", { name: "Konfigurácia", exact: true }).click();
  await expect(page.locator('[data-key="name"]')).toBeDisabled();
  await page.getByRole("button", { name: "Prehľad", exact: true }).click();
  await page.locator('[data-cover="two"]').dispatchEvent("pointerdown", {
    pointerType: "touch",
    pointerId: 8,
    isPrimary: true,
    button: 0,
  });
  await page.waitForTimeout(600);
  await page.locator('[data-cover="two"]').dispatchEvent("pointerup", {
    pointerType: "touch",
    pointerId: 8,
    isPrimary: true,
    button: 0,
  });
  await expect(page.locator('[data-row="two"]')).not.toHaveClass(
    /multi-selected/,
  );
});

test("history period is selectable", async ({ page }) => {
  await page.getByLabel("Obdobie histórie").selectOption("6");
  await expect(
    page.getByRole("heading", { name: "História polohy a režimov" }),
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
  await page.evaluate(() => window.publish({ entry_id: "one", removed: true }));
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
  await expect(page.locator('[data-cover="two"]')).toBeVisible();
  await expect(page.getByText("58 %", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "Konfigurácia", exact: true }).click();
  await expect(page.locator('[data-cover="two"]')).toBeVisible();
});

test("overview exposes one-shot phase controls and sends the matching action", async ({
  page,
}) => {
  await page.evaluate(() => {
    const controller = window.fixture.controllers[0];
    controller.config.shading_enabled = true;
    controller.config.ventilation_enabled = true;
    controller.runtime.shading = false;
    controller.decision.mode = "idle";
    window.publish({ controller });
  });

  await page.getByRole("button", { name: "Začať tienenie teraz" }).click();
  await expect
    .poll(() =>
      page.evaluate(() =>
        window.calls.some(
          (call) =>
            call.type === "cca_zaluzie/control" &&
            call.action === "phase_shade_start",
        ),
      ),
    )
    .toBe(true);

  await page.evaluate(() => {
    const controller = window.fixture.controllers[0];
    controller.runtime.shading = true;
    controller.decision.mode = "shading";
    window.publish({ controller });
  });
  await expect(
    page.getByRole("button", { name: "Ukončiť tienenie dnes" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Začať vetranie" }),
  ).toBeVisible();
});

test("overview explains the post-close protection and labels its one-time release", async ({
  page,
}) => {
  await page.evaluate(() => {
    const controller = window.fixture.controllers[0];
    const now = Date.now() / 1000;
    controller.config.window_open = "binary_sensor.passage";
    controller.config.contact_lockout_enabled = true;
    controller.runtime.contact_lockout_until = now + 1200;
    controller.runtime.contact_closed_verified_at = now - 5;
    controller.sensors["binary_sensor.passage"] = {
      state: "off",
      attributes: {},
    };
    controller.server_time = now;
    window.publish({ controller });
  });

  await expect(page.getByText("Ochrana po zatvorení kontaktu")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "↓ Zatvoriť · jednorazovo" }),
  ).toBeEnabled();
  await expect(page.locator("#manual-position")).toBeDisabled();
  await page.getByRole("button", { name: "↓ Zatvoriť · jednorazovo" }).click();
  await expect
    .poll(() =>
      page.evaluate(() =>
        window.calls.some(
          (call) =>
            call.type === "cca_zaluzie/control" && call.action === "close",
        ),
      ),
    )
    .toBe(true);
});

test("one-time close stays disabled when the contact changed after verification", async ({
  page,
}) => {
  await page.evaluate(() => {
    const controller = window.fixture.controllers[0];
    const now = Date.now() / 1000;
    controller.config.window_open = "binary_sensor.passage";
    controller.config.contact_lockout_enabled = true;
    controller.runtime.contact_lockout_until = now + 1200;
    controller.runtime.contact_closed_verified_at = now - 10;
    controller.sensors["binary_sensor.passage"] = {
      state: "off",
      changed_at: now - 2,
      attributes: {},
    };
    controller.server_time = now;
    window.publish({ controller });
  });

  await expect(
    page.getByRole("button", { name: "↓ Zatvoriť", exact: true }),
  ).toBeDisabled();
  await expect(page.locator("#manual-position")).toBeDisabled();
});

test("retains separate drafts across covers and sections", async ({ page }) => {
  await page.getByRole("button", { name: "Konfigurácia", exact: true }).click();
  await page.getByLabel("Názov", { exact: true }).fill("Môj balkón");
  await page.getByRole("button", { name: "Ráno a večer", exact: true }).click();
  await page.locator('[data-cover="two"]').click();
  await page.getByRole("button", { name: "Žalúzia", exact: true }).click();
  await expect(page.getByLabel("Názov", { exact: true })).toHaveValue(
    "Spálňa · okno",
  );
  await page.locator('[data-cover="one"]').click();
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
  await page
    .getByRole("button", { name: "Spustiť reset", exact: true })
    .click();
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
  await page.getByRole("button", { name: "↓ Zatvoriť", exact: true }).click();
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
  await page.getByRole("button", { name: "Konfigurácia", exact: true }).click();
  await page
    .getByRole("button", { name: "Vypnúť simuláciu", exact: true })
    .click();
  await expect
    .poll(() =>
      page.evaluate(() =>
        window.calls.some(
          (c) =>
            c.type === "cca_zaluzie/control" && c.action === "simulation_off",
        ),
      ),
    )
    .toBe(true);
});

test("overview shows the calculated movement and live and projected sun values", async ({
  page,
}) => {
  await page.evaluate(() => {
    window.fixture.prediction = {
      events: [
        {
          scenario_at: new Date(Date.now() + 3600000).toISOString(),
          type: "open",
          target: 100,
          status: "conditional",
          solar: { azimuth: 101.2, elevation: -2.8 },
          conditions: {
            inputs: {
              "sun.sun": {
                state: "below_horizon",
                attributes: { azimuth: 101.2, elevation: -2.8 },
              },
              "binary_sensor.window": { state: "off" },
            },
            thresholds: { sun_open: -3 },
            "light.open.sun": true,
          },
          assumptions: [
            "Jas bude priaznivý scenár.",
            "Budúca hodnota binary_sensor.window nie je známa.",
          ],
        },
      ],
    };
    const controller = window.fixture.controllers[0];
    controller.config.sun_enabled = true;
    controller.config.sun_sensor = "sun.sun";
    controller.config.ventilation_enabled = true;
    controller.config.window_open = "binary_sensor.window";
    controller.sensors["sun.sun"] = {
      state: "below_horizon",
      attributes: { azimuth: 84.2, elevation: -17.0 },
    };
    controller.sensors["binary_sensor.window"] = { state: "on" };
    controller.decision.conditions = {
      inputs: {
        "sun.sun": {
          state: "below_horizon",
          attributes: { azimuth: 84.2, elevation: -17.0 },
        },
        "binary_sensor.window": { state: "on" },
      },
      thresholds: { sun_open: -3 },
      "light.open.sun": false,
    };
    window.publish({ controller });
  });

  await expect(page.getByText("Vypočítaný ďalší pohyb")).toBeVisible();
  await expect(
    page.getByText("Aktuálne: azimut 84,2° · výška −17°"),
  ).toBeVisible();
  await expect(
    page.getByText("Pri pohybe: azimut 101,2° · výška −2,8°"),
  ).toBeVisible();
  await expect(
    page.getByText("Hranica výšky slnka pre otvorenie: ≥ −3°"),
  ).toBeVisible();
  await expect(
    page.getByText("Teraz: nesplnená · pri pohybe: splnená"),
  ).toBeVisible();
  await expect(page.getByText("Jas bude priaznivý scenár.")).toBeVisible();
  await expect(
    page.getByText("Teraz: on · pri pohybe: neznáma hodnota"),
  ).toBeVisible();
  const call = await page.evaluate(() =>
    window.calls.find((c) => c.type === "cca_zaluzie/predict"),
  );
  expect(call.from_now).toBe(true);
});
