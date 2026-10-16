import { test, expect } from "@playwright/test";
test.beforeEach(async ({ page }) => {
  await page.goto("/tests/browser/demo.html");
  await page.waitForFunction(() => typeof window.publish === "function");
});
test("transient null and order updates preserve selected cover and draft", async ({
  page,
}) => {
  await page.locator('[data-cover="two"]').click();
  await page.getByRole("button", { name: "Konfigurácia", exact: true }).click();
  await page.locator('[data-key="name"]').fill("Rozpracované");
  await page.evaluate(() => {
    window.publish({ entry_id: "two", controller: null });
    window.publish({ order: ["two", "one", "three"], order_revision: 2 });
  });
  await expect(page.locator('[data-key="name"]')).toHaveValue("Rozpracované");
  await expect(page.locator('[data-cover="two"]')).toHaveAttribute(
    "aria-pressed",
    "true",
  );
});
test("visible drag grip supports persisted keyboard reorder without changing focus", async ({
  page,
}) => {
  const grip = page.locator('[data-grip="one"]');
  await expect(grip).toBeVisible();
  await grip.focus();
  await grip.press("ArrowDown");
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          window.calls.findLast((c) => c.type === "cca_zaluzie/reorder")
            ?.entry_ids,
      ),
    )
    .toEqual(["two", "one", "three"]);
  await expect(page.locator('[data-cover="one"]')).toHaveAttribute(
    "aria-pressed",
    "true",
  );
});
test("ctrl selection keeps focus and bulk patches only explicitly edited allowlisted fields", async ({
  page,
}) => {
  await page.locator('[data-cover="two"]').click({ modifiers: ["Control"] });
  await expect(page.locator('[data-cover="one"]')).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await page.getByRole("button", { name: "Konfigurácia", exact: true }).click();
  await expect(page.locator('[data-key="name"]')).toBeDisabled();
  await expect(page.locator('[data-key="cover_entity"]')).toBeDisabled();
  await page.getByRole("button", { name: "Ráno a večer", exact: true }).click();
  await expect(page.locator('[data-key="morning_early"]')).toHaveValue("");
  await page.locator('[data-key="morning_late"]').fill("09:15");
  await page.getByRole("button", { name: /Uložiť zmeny/ }).click();
  await page
    .getByRole("button", { name: "Potvrdiť hromadné uloženie" })
    .click();
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          window.calls.findLast((c) => c.type === "cca_zaluzie/configure_bulk")
            ?.patch,
      ),
    )
    .toEqual({ morning_late: "09:15" });
});
test("history reads actual endpoint, preserves gaps and overview requests a live prediction", async ({
  page,
}) => {
  await expect(page.getByLabel("Obdobie histórie")).toHaveCount(0);
  await expect
    .poll(() =>
      page.evaluate(() =>
        window.calls.some(
          (c) => c.type === "cca_zaluzie/history" && c.hours === 24,
        ),
      ),
    )
    .toBe(true);
  await expect(page.locator(".history-gap").first()).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(() =>
        window.calls.some(
          (c) => c.type === "cca_zaluzie/predict" && c.from_now === true,
        ),
      ),
    )
    .toBe(true);
});
test("movement triangle uses active direction and saved toast expires", async ({
  page,
}) => {
  await page.evaluate(() => {
    const c = window.fixture.controllers[0];
    c.motion = {
      status: "closing",
      direction: "closing",
      target: 0,
      source: "cover_entity",
      simulated: false,
    };
    window.publish({ controller: c });
  });
  await expect(
    page.locator('[data-direction="closing"]').first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Konfigurácia", exact: true }).click();
  await page.locator('[data-key="name"]').fill("Uložené");
  await page.getByRole("button", { name: "Uložiť zmeny", exact: true }).click();
  await expect(page.locator(".toast")).toBeVisible();
  await expect(page.locator(".toast")).toHaveCount(0, { timeout: 5500 });
});
test("all schema controls stay represented and main switches are in feature headers", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Konfigurácia", exact: true }).click();
  const keys = await page.evaluate(() => Object.keys(window.fixture.fields));
  const represented = new Set();
  for (const group of await page.evaluate(() =>
    Object.keys(window.fixture.groups),
  )) {
    await page.locator(`[data-group="${group}"]`).click();
    for (const key of await page
      .locator("[data-key]")
      .evaluateAll((es) => es.map((e) => e.dataset.key)))
      represented.add(key);
  }
  expect(keys.filter((k) => !represented.has(k))).toEqual([]);
  await page.locator('[data-group="schedule"]').click();
  await expect(
    page.locator('.feature-header [data-key="time_enabled"]'),
  ).toBeVisible();
});
test("native HA controls receive locale and duration event values in seconds", async ({
  page,
}) => {
  await page.evaluate(() => {
    for (const tag of [
      "ha-time-input",
      "ha-duration-input",
      "ha-switch",
      "ha-entity-picker",
      "ha-selector",
    ])
      if (!customElements.get(tag))
        customElements.define(tag, class extends HTMLElement {});
    const p = document.querySelector("cca-zaluzie-panel");
    p.hass.locale = { language: "sk", time_format: "24" };
  });
  await page.getByRole("button", { name: "Konfigurácia", exact: true }).click();
  await page.locator('[data-group="schedule"]').click();
  expect(
    await page
      .locator("ha-time-input")
      .first()
      .evaluate((e) => e.locale?.language),
  ).toBe("sk");
  await page.locator('[data-group="manual"]').click();
  await page.locator('[data-key="manual_timeout"]').evaluate((e) =>
    e.dispatchEvent(
      new CustomEvent("value-changed", {
        bubbles: true,
        composed: true,
        detail: { value: { hours: 0, minutes: 12, seconds: 5 } },
      }),
    ),
  );
  await page.locator("[data-save]").click();
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          window.calls.findLast((c) => c.type === "cca_zaluzie/configure")
            ?.config.manual_timeout,
      ),
    )
    .toBe(725);
});
test("bulk save preserves existing isolated drafts and captured stale revision", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Konfigurácia", exact: true }).click();
  await page.locator('[data-key="name"]').fill("Izolovaný návrh");
  await page.locator('[data-cover="two"]').click({ modifiers: ["Control"] });
  await page.locator('[data-group="schedule"]').click();
  await page.locator('[data-key="morning_late"]').fill("09:20");
  const revision = await page.evaluate(
    () => window.fixture.controllers[0].config_revision,
  );
  await page.evaluate(() => {
    const c = structuredClone(window.fixture.controllers[0]);
    c.config_revision = "changed-in-other-session";
    window.publish({ controller: c });
  });
  await page.locator("[data-save]").click();
  await page.locator("[data-confirm-bulk]").click();
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          window.calls.findLast((c) => c.type === "cca_zaluzie/configure_bulk")
            ?.revisions.one,
      ),
    )
    .toBe(revision);
  await page.locator("[data-clear-selection]").click();
  await page.locator('[data-group="cover"]').click();
  await expect(page.locator('[data-key="name"]')).toHaveValue(
    "Izolovaný návrh",
  );
});
test("dragging shows drop target and persists actual new order", async ({
  page,
}) => {
  await page.locator('[data-grip="one"]').dispatchEvent("dragstart", {
    dataTransfer: await page.evaluateHandle(() => new DataTransfer()),
  });
  await page.locator('[data-row="two"]').dispatchEvent("dragover");
  await expect(page.locator('[data-row="two"]')).toHaveClass(/drop-target/);
  await page.locator('[data-row="two"]').dispatchEvent("drop");
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          window.calls.findLast((c) => c.type === "cca_zaluzie/reorder")
            ?.entry_ids,
      ),
    )
    .toEqual(["two", "one", "three"]);
});
test("unknown observed direction is not inferred from target", async ({
  page,
}) => {
  await page.evaluate(() => {
    const c = window.fixture.controllers[0];
    c.last_movement = null;
    c.decision.target = 0;
    window.publish({ controller: c });
  });
  await expect(
    page.locator(
      '[data-row="one"] [data-direction], .position-layout [data-direction]',
    ),
  ).toHaveCount(0);
});
test("actual production layout screenshots and mobile overflow", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({
    path: "test-results/production-overview.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Konfigurácia", exact: true }).click();
  await page.locator('[data-group="schedule"]').click();
  await page.screenshot({
    path: "test-results/production-schedule.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth))
    .toBeLessThanOrEqual(390);
  await page.screenshot({
    path: "test-results/production-mobile.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.evaluate(() => {
    const p = document.querySelector("cca-zaluzie-panel");
    p.style.setProperty("--card-background-color", "#1b252d");
    p.style.setProperty("--primary-background-color", "#10171d");
    p.style.setProperty("--primary-text-color", "#e4edf4");
    p.style.setProperty("--secondary-text-color", "#9faeba");
    p.style.setProperty("--divider-color", "#35434e");
    p.style.setProperty("--primary-color", "#66c9fa");
  });
  await page.screenshot({
    path: "test-results/production-dark.png",
    fullPage: true,
  });
});
test("discard after another session update uses latest baseline and revision", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Konfigurácia", exact: true }).click();
  await page.locator('[data-key="name"]').fill("Local draft");
  await page.evaluate(() => {
    const c = structuredClone(window.fixture.controllers[0]);
    c.config.name = "Latest saved";
    c.config_revision = "latest-revision";
    window.fixture.controllers[0] = c;
    window.publish({ controller: c });
  });
  await page.locator("[data-discard]").click();
  await expect(page.locator('[data-key="name"]')).toHaveValue("Latest saved");
  await page.locator('[data-key="name"]').fill("Next edit");
  await page.locator("[data-save]").click();
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          window.calls.findLast((c) => c.type === "cca_zaluzie/configure")
            ?.expected_revision,
      ),
    )
    .toBe("latest-revision");
});
test("new measured position and event appear through live subscription", async ({
  page,
}) => {
  await page.evaluate(() => {
    const c = structuredClone(window.fixture.controllers[0]);
    c.position_history = [
      { at: new Date().toISOString(), position: 37, available: true },
    ];
    c.events.push({
      id: "fresh",
      at: new Date().toISOString(),
      type: "command_completed",
      details: { target: 37, reason: "Aktuálne meranie" },
    });
    window.publish({ controller: c });
  });
  await expect(
    page.getByRole("button", { name: /Aktuálne meranie/ }),
  ).toBeVisible();
  await expect(page.locator(".measured-line")).toHaveAttribute("d", /L/);
  await expect(page.locator("svg circle")).toHaveCount(0);
  await page.getByRole("button", { name: /Aktuálne meranie/ }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("dialog")).toContainText("Aktuálne meranie");
});

test("bulk save rebases only actual local edits onto another session's config", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Konfigurácia", exact: true }).click();
  await page.locator('[data-key="name"]').fill("Local name");
  await page.evaluate(() => {
    const c = structuredClone(window.fixture.controllers[0]);
    c.config.morning_early = "07:45";
    c.config_revision = "remote-revision";
    window.fixture.controllers[0] = c;
    window.publish({ controller: c });
  });
  await page.locator('[data-cover="two"]').click({ modifiers: ["Control"] });
  await page.locator('[data-group="schedule"]').click();
  await page.locator('[data-key="morning_late"]').fill("09:20");
  await page.locator("[data-save]").click();
  await page.locator("[data-confirm-bulk]").click();
  await expect(page.locator(".toast")).toBeVisible();
  await page.locator("[data-clear-selection]").click();
  await expect(page.locator('[data-key="morning_early"]')).toHaveValue("07:45");
  await page.locator('[data-group="cover"]').click();
  await expect(page.locator('[data-key="name"]')).toHaveValue("Local name");
});

test("post-save refresh cannot adopt a newer revision for an isolated dirty draft", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Konfigurácia", exact: true }).click();
  await page.locator('[data-key="name"]').fill("Local name");
  await page.evaluate(() => {
    const p = document.querySelector("cca-zaluzie-panel");
    const call = p.hass.callWS;
    let afterBulk = false;
    p.hass.callWS = async (msg) => {
      if (msg.type === "cca_zaluzie/list" && afterBulk) {
        window.fixture.controllers[0].config.morning_early = "07:45";
        window.fixture.controllers[0].config_revision = "newer-remote";
      }
      const result = await call(msg);
      if (msg.type === "cca_zaluzie/configure_bulk") {
        result.config_revisions = { one: "saved-bulk", two: "saved-two" };
        afterBulk = true;
      }
      return result;
    };
  });
  await page.locator('[data-cover="two"]').click({ modifiers: ["Control"] });
  await page.locator('[data-group="schedule"]').click();
  await page.locator('[data-key="morning_late"]').fill("09:20");
  await page.locator("[data-save]").click();
  await page.locator("[data-confirm-bulk]").click();
  await expect(page.locator(".toast")).toBeVisible();
  await page.locator("[data-clear-selection]").click();
  await page.locator("[data-save]").click();
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          window.calls.findLast((c) => c.type === "cca_zaluzie/configure")
            ?.expected_revision,
      ),
    )
    .toBe("saved-bulk");
});
test("bulk confirmation accurately describes false values and disables protected fields", async ({
  page,
}) => {
  await page.locator('[data-cover="two"]').click({ modifiers: ["Control"] });
  await page.getByRole("button", { name: "Konfigurácia", exact: true }).click();
  await page.locator('[data-group="schedule"]').click();
  await page.locator('[data-key="time_enabled"]').uncheck();
  await page.locator("[data-save]").click();
  await expect(page.getByRole("dialog")).toContainText("Vypnuté");
});
test("reconnect and repeated keyboard reorder keep focus and selected draft stable", async ({
  page,
}) => {
  const grip = page.locator('[data-grip="one"]');
  await grip.focus();
  await grip.press("ArrowDown");
  await expect(grip).toBeFocused();
  await grip.press("ArrowDown");
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          window.calls.findLast((c) => c.type === "cca_zaluzie/reorder")
            ?.entry_ids,
      ),
    )
    .toEqual(["two", "three", "one"]);
  await page.getByRole("button", { name: "Konfigurácia", exact: true }).click();
  await page.locator('[data-key="name"]').fill("Reconnect draft");
  await page.evaluate(() => {
    const p = document.querySelector("cca-zaluzie-panel"),
      h = p.hass;
    p.hass = { ...h, connection: { ...h.connection } };
  });
  await expect(page.locator('[data-key="name"]')).toHaveValue(
    "Reconnect draft",
  );
  await expect(page.locator('[data-cover="one"]')).toHaveAttribute(
    "aria-pressed",
    "true",
  );
});
test("native position slider and exact numeric control keep safety control contract", async ({
  page,
}) => {
  await page.evaluate(() => {
    customElements.define("ha-slider", class extends HTMLElement {});
    const p = document.querySelector("cca-zaluzie-panel");
    p._render();
  });
  await page.locator("ha-slider[data-position]").evaluate((e) => {
    e.value = 41;
    e.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await expect
    .poll(() =>
      page.evaluate(() =>
        window.calls.findLast((c) => c.type === "cca_zaluzie/control"),
      ),
    )
    .toMatchObject({ action: "position", entry_id: "one", position: 41 });
  await page.locator('input[type="number"][data-position]').fill("32");
  await page.locator('input[type="number"][data-position]').press("Tab");
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          window.calls.findLast((c) => c.type === "cca_zaluzie/control")
            ?.position,
      ),
    )
    .toBe(32);
});
test("complete history retains mode and protection events and filters simulation", async ({
  page,
}) => {
  await page.evaluate(() => {
    const c = window.fixture.controllers[0];
    for (const [id, type, details, simulated] of [
      ["mode", "decision", { mode: "shading" }, false],
      ["manual", "manual_detected", { position: 30 }, false],
      ["block", "decision", { inhibit: "paused" }, false],
      ["sim", "would_dispatch", { target: 42 }, true],
      ["simerr", "command_failed", { error: "Simulovaná chyba" }, true],
    ])
      c.events.push({
        id,
        type,
        details,
        simulated,
        at: new Date().toISOString(),
      });
    window.publish({ controller: c });
  });
  await expect(page.locator(".recorded-tracks")).toHaveCount(0);
  await expect(
    page.locator('.useful-history [data-event="manual"]'),
  ).toBeVisible();
  await page.locator("[data-all-events]").click();
  await expect(page.locator('dialog [data-event="mode"]')).toBeVisible();
  await expect(page.locator('dialog [data-event="block"]')).toBeVisible();
  await page.locator(".simulation-trace summary").click();
  await page.getByLabel("Filtrovať simuláciu").selectOption("errors");
  await expect(page.locator(".simulation-trace")).toContainText(
    "Simulovaná chyba",
  );
  await expect(
    page.locator('.simulation-trace [data-event="sim"]'),
  ).toHaveCount(0);
});
