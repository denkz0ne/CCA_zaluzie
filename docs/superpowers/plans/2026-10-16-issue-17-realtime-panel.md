# Issue #17 Realtime Panel Implementation Plan

> **For agentic workers:** implementation is being executed natively in this Codex session. The steps below use checkbox syntax and must be updated as work completes.

**Goal:** Keep the HA side panel stable during live updates while showing real motion, compacting the cover list, surfacing phase actions, and localizing user-facing actions.

**Architecture:** Keep the existing HA WebSocket API and event delegation. Replace destructive full-root/list rebuilds during routine snapshots with a lightweight keyed DOM reconciler that preserves focused/editing controls and only patches changed nodes. Add a read-only motion descriptor to controller snapshots from authoritative HA state, the existing command lifecycle, and explicitly marked simulation state.

**Tech Stack:** Home Assistant Python integration, native JavaScript custom element, CSS, pytest, Playwright.

**Spec:** GitHub issue [#17](https://github.com/denkz0ne/CCA_zaluzie/issues/17) and repository `AGENTS.md`.

## Global Constraints

- Keep motor service calls behind the existing controller/operations gateway.
- Never synthesize measured position; expose estimated or simulated position only with its existing label.
- Preserve draft configuration, selection, scroll, drag state, dialogs, tabs, and safety controls across WebSocket updates.
- Do not access live Home Assistant or actuate physical motors.

## Review Focus

- Reused input nodes: a live update must not overwrite a focused user edit.
- Reordered keyed rows: focus and active drag state must survive routine updates.
- HA reports only `opening`/`closing`: show direction and target while keeping last confirmed position.
- Command starts/stops/fails: never leave stale motion indicator visible.
- Unknown prediction action: show a human-readable fallback and never emit the raw internal key.

---

### Task 1: Keyed, non-destructive snapshot updates

**Files:**
- Modify: `custom_components/cca_zaluzie/frontend/cca-zaluzie-panel.js`
- Test: `tests/browser/panel.spec.mjs`

- [x] Add tests retaining the root, cover row, focused input, and open dialog after repeated pushes; existing position-control and scroll coverage remains active.
- [x] Verify the new regression tests fail against destructive rendering.
- [x] Add keyed DOM reconciliation, frame-coalesced updates, stable focus/dialog handling, and skip unchanged snapshots.
- [x] Keep countdown changes confined to existing text nodes and load prediction only when inputs or minute change.
- [x] Run the targeted and full browser suite.

### Task 2: Authoritative live motion status

**Files:**
- Modify: `custom_components/cca_zaluzie/controller.py`, `custom_components/cca_zaluzie/frontend/cca-zaluzie-panel.js`
- Test: `tests/test_integration.py`, `tests/browser/panel.spec.mjs`

- [x] Add HA snapshot coverage for entity motion, requested/moving commands, and explicitly marked simulation.
- [x] Expose direction/status/target/source independently from measured position.
- [x] Render direction and target separately; keep estimated/simulated positions labeled and never substitute the target for measured position.
- [x] Run browser coverage locally and verify all HA lifecycle tests in the passing Linux CI matrix (2026.9.4, 2026.10.0, 2026.10.1).

### Task 3: Compact keyed cover list and quick actions

**Files:**
- Modify: `custom_components/cca_zaluzie/frontend/cca-zaluzie-panel.js`, `custom_components/cca_zaluzie/frontend/panel.css`
- Test: `tests/browser/redesign.spec.mjs`, `tests/browser/panel.spec.mjs`

- [x] Test compact cards, accessible grip, keyboard reorder, Ctrl/Cmd selection, touch long-press selection, and keyed row stability.
- [x] Remove the checkbox row and visible reorder arrows/text; retain stored order and keyboard movement.
- [x] Add one phase action region beside the main position controls using the existing action IDs.
- [x] Run the complete browser suite including the existing desktop and mobile viewport checks.

### Task 4: Human-readable action names and release docs

**Files:**
- Modify: `custom_components/cca_zaluzie/frontend/cca-zaluzie-panel.js`, `CHANGELOG.md`, `docs/PANEL.md`, `docs/FEATURE_MATRIX.md`
- Test: `tests/browser/panel.spec.mjs`

- [x] Localize schedule, shading, ventilation and action events with a safe readable fallback for unknown action types.
- [x] Distinguish scheduled opening/closing from generic and protective closing; display target alongside movement.
- [x] Document issue #17 mechanics and update current version/changelog.

### Task 5: Verification and delivery

- [x] Run Python tests in GitHub Actions, Ruff, Prettier, the complete 46-test Playwright suite and `git diff --check`.
- [x] Review the diff; motor execution logic and live Home Assistant were not touched.
- [x] Merge focused PR [#18](https://github.com/denkz0ne/CCA_zaluzie/pull/18), pass GitHub Actions, publish [2026.12.4](https://github.com/denkz0ne/CCA_zaluzie/releases/tag/2026.12.4), and close issue #17.
