import { test, expect } from "@playwright/test";

async function load(page) {
  await page.goto("/tests/browser/demo.html");
  await page.waitForFunction(() => typeof window.publish === "function");
}

test("unavailable feedback cannot leave an old motion indicator running", async ({
  page,
}) => {
  await load(page);
  await page.evaluate(() => {
    const c = window.fixture.controllers[0];
    c.available = false;
    c.position = null;
    c.motion = { status: "moving", direction: "opening", target: 100 };
    window.publish({ controller: c });
  });
  await expect(page.locator('[data-cover="one"] .badge')).toHaveText(
    "Nedostupná",
  );
  await expect(page.locator("[data-direction]")).toHaveCount(0);
  await expect(page.locator(".motion-status")).toHaveCount(0);
});

for (const [action, shading, mode] of [
  ["phase_shade_start", false, "idle"],
  ["phase_shade_end", true, "shading"],
  ["phase_vent_start", false, "idle"],
  ["phase_vent_end", false, "ventilation"],
]) {
  test(`phase button ${action} sends exactly one phase command`, async ({
    page,
  }) => {
    await load(page);
    await page.evaluate(
      ({ shading, mode }) => {
        const c = window.fixture.controllers[0];
        c.config.shading_enabled = true;
        c.config.ventilation_enabled = true;
        c.runtime.shading = shading;
        c.decision.mode = mode;
        window.publish({ controller: c });
      },
      { shading, mode },
    );
    await page.locator(`.phase-controls [data-action="${action}"]`).click();
    await expect
      .poll(() =>
        page.evaluate(() =>
          window.calls.filter((c) => c.type === "cca_zaluzie/control"),
        ),
      )
      .toEqual([{ type: "cca_zaluzie/control", entry_id: "one", action }]);
  });
}

test("100 live position frames update values without remounts or repeated predictions", async ({
  page,
}) => {
  await load(page);
  const result = await page.evaluate(async () => {
    const p = document.querySelector("cca-zaluzie-panel");
    const root = p.shadowRoot;
    const stable = [
      "main.layout",
      '[data-row="one"]',
      '[data-grip="one"]',
      '[data-action="open"]',
      "#manual-position",
      "link[rel=stylesheet]",
    ];
    const refs = stable.map((s) => root.querySelector(s));
    const before = window.calls.filter(
      (c) => c.type === "cca_zaluzie/predict",
    ).length;
    for (let position = 0; position < 100; position++) {
      const c = structuredClone(window.fixture.controllers[0]);
      c.position = position;
      c.motion = {
        status: "opening",
        direction: "opening",
        target: 100,
        simulated: false,
      };
      c.decision.conditions = {
        inputs: {
          [c.cover_entity]: {
            state: "opening",
            attributes: { current_position: position },
          },
        },
      };
      window.publish({ controller: c });
      await new Promise(requestAnimationFrame);
      if (
        stable.some((selector, i) => root.querySelector(selector) !== refs[i])
      )
        return { error: "A stable control was replaced" };
      if (
        !root
          .querySelector(".position-number")
          .textContent.includes(String(position))
      )
        return { error: "Detail did not update" };
      if (
        !root
          .querySelector('[data-cover="one"] .cover-number')
          .textContent.includes(String(position))
      )
        return { error: "Sidebar did not update" };
    }
    return {
      error: null,
      predictions:
        window.calls.filter((c) => c.type === "cca_zaluzie/predict").length -
        before,
    };
  });
  expect(result.error).toBeNull();
  expect(result.predictions).toBeLessThanOrEqual(2);
  await expect(
    page.locator('[data-cover="one"] [data-direction="opening"]'),
  ).toBeVisible();
  await page.evaluate(() => {
    const c = structuredClone(window.fixture.controllers[0]);
    c.position = 100;
    c.motion = { status: "idle", direction: null, target: null };
    window.publish({ controller: c });
  });
  await expect(page.locator('[data-direction="opening"]')).toHaveCount(0);
  await expect(page.locator(".position-number")).toContainText("100");
});

test("a live snapshot preserves the insertion marker while dragging a card", async ({
  page,
}) => {
  await load(page);
  await page.evaluate(async () => {
    const p = document.querySelector("cca-zaluzie-panel");
    const grip = p.shadowRoot.querySelector('[data-grip="one"]');
    const row = p.shadowRoot.querySelector('[data-row="three"]');
    const transfer = new DataTransfer();
    grip.dispatchEvent(
      new DragEvent("dragstart", { bubbles: true, dataTransfer: transfer }),
    );
    row.dispatchEvent(
      new DragEvent("dragover", {
        bubbles: true,
        cancelable: true,
        dataTransfer: transfer,
      }),
    );
    window.dragTransfer = transfer;
    const c = structuredClone(window.fixture.controllers[0]);
    c.position = 43;
    window.publish({ controller: c });
    await new Promise(requestAnimationFrame);
  });
  await expect(page.locator('[data-row="three"]')).toHaveClass(/drop-target/);
  await page.locator('[data-row="three"]').evaluate((row) =>
    row.dispatchEvent(
      new DragEvent("drop", {
        bubbles: true,
        cancelable: true,
        dataTransfer: window.dragTransfer,
      }),
    ),
  );
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          window.calls.findLast((c) => c.type === "cca_zaluzie/reorder")
            ?.entry_ids,
      ),
    )
    .toEqual(["two", "three", "one"]);
});

test("upgrade cannot reuse the legacy full-height grip stylesheet and clip cover cards", async ({
  page,
}) => {
  await page.route("**/demo.html", async (route) => {
    const response = await route.fetch();
    await route.fulfill({
      response,
      body: (await response.text()).replace(
        'cca-zaluzie-panel.js"',
        'cca-zaluzie-panel.js?v=upgrade-regression"',
      ),
    });
  });
  await page.route("**/panel.css*", async (route) => {
    const response = await route.fetch();
    const legacy = new URL(route.request().url()).searchParams.has("v")
      ? ""
      : `
      /* Browser still holds the 2026.12.3 grip rules under the unversioned URL. */
      .drag-grip { position: static; transform: none; width: auto; height: 100%;
        display: flex; flex: 1; padding: 3px 8px; }
    `;
    await route.fulfill({ response, body: (await response.text()) + legacy });
  });
  await load(page);
  const card = page.locator('[data-row="one"]');
  await expect
    .poll(() =>
      card.evaluate((e) => {
        const bounds = e.getBoundingClientRect();
        const grip = e.querySelector("[data-grip]").getBoundingClientRect();
        const name = e.querySelector(".cover-name").getBoundingClientRect();
        return (
          bounds.height <= 140 &&
          grip.height <= 24 &&
          name.bottom <= bounds.bottom &&
          grip.top <= bounds.top + 2
        );
      }),
    )
    .toBe(true);
  await card.getByText("Obývačka · balkón").click();
  await expect(page.locator(".context .name")).toHaveText("Obývačka · balkón");
});

test("phase start and end are visible paired buttons below the position control", async ({
  page,
}) => {
  await load(page);
  await page.evaluate(() => {
    const c = window.fixture.controllers[0];
    c.config.shading_enabled = true;
    c.config.ventilation_enabled = true;
    c.runtime.shading = false;
    c.decision.mode = "idle";
    window.publish({ controller: c });
  });
  const region = page.getByRole("region", {
    name: "Jednorazové zmeny režimov",
  });
  await expect(region).toBeVisible();
  await expect(
    region.locator('[data-action="phase_shade_start"]'),
  ).toBeEnabled();
  await expect(
    region.locator('[data-action="phase_shade_end"]'),
  ).toBeDisabled();
  await expect(
    region.locator('[data-action="phase_vent_start"]'),
  ).toBeEnabled();
  await expect(region.locator('[data-action="phase_vent_end"]')).toBeDisabled();
  const end = await page.locator(".range-ends").boundingBox();
  const bounds = await region.boundingBox();
  expect(bounds.y).toBeGreaterThan(end.y);
  for (const action of await region.locator("button").all()) {
    const b = await action.boundingBox();
    expect(b.height).toBeGreaterThanOrEqual(40);
    await expect(action).toHaveAttribute("title", /.+/);
    await expect(action.locator("svg")).toBeVisible();
  }
  await page.screenshot({
    path: "test-results/issue17-phase-buttons-desktop.png",
    fullPage: true,
  });
});

test("disabled modes retain discoverable controls with the reason they cannot start", async ({
  page,
}) => {
  await load(page);
  await page.evaluate(() => {
    const c = window.fixture.controllers[0];
    c.config.shading_enabled = false;
    c.config.ventilation_enabled = false;
    c.runtime.shading = false;
    window.publish({ controller: c });
  });
  const region = page.getByRole("region", {
    name: "Jednorazové zmeny režimov",
  });
  await expect(region).toBeVisible();
  await expect(region.locator("button")).toHaveCount(4);
  for (const button of await region.locator("button").all())
    await expect(button).toBeDisabled();
  await expect(region).toContainText("Vypnuté v konfigurácii");
});

test("phase changes invalidate the next movement calculation in the same minute", async ({
  page,
}) => {
  await load(page);
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          window.calls.filter((c) => c.type === "cca_zaluzie/predict").length,
      ),
    )
    .toBe(1);
  await page.evaluate(() => {
    const c = structuredClone(window.fixture.controllers[0]);
    c.runtime.phase_latches = {
      shade_end: new Date().toISOString().slice(0, 10),
    };
    c.runtime.shading = false;
    c.decision.mode = "schedule";
    window.publish({ controller: c });
  });
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          window.calls.filter((c) => c.type === "cca_zaluzie/predict").length,
      ),
    )
    .toBe(2);
});

test("live measured values never reset a focused native slider while a user chooses a position", async ({
  page,
}) => {
  await load(page);
  await page.evaluate(() => {
    customElements.define("ha-slider", class extends HTMLElement {});
    const p = document.querySelector("cca-zaluzie-panel");
    p._render();
    const slider = p.shadowRoot.querySelector("ha-slider");
    slider.tabIndex = 0;
    slider.focus();
    slider.value = 73;
    window.chosenSlider = slider;
    const c = structuredClone(window.fixture.controllers[0]);
    c.position = 61;
    c.motion = {
      status: "opening",
      direction: "opening",
      target: 100,
      simulated: false,
    };
    window.publish({ controller: c });
  });
  await expect(page.locator(".position-number")).toContainText("61");
  await expect
    .poll(() => page.evaluate(() => window.chosenSlider.value))
    .toBe(73);
  await expect(page.locator("ha-slider")).toBeFocused();
});
