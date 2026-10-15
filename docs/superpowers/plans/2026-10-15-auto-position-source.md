# Automatic Position Source Implementation Plan

> **For agentic workers:** Implement inline in this session, task by task, using test-driven development.

**Goal:** Automatically choose reliable cover position feedback, hide the selector while it works, and expose manual source selection when detection is missing or ambiguous.

**Architecture:** A pure detector inspects numeric `current_position` and `position` attributes. Controllers in automatic mode resolve the source from live state and share that result with the engine, operations, prediction, config UI and panel. Custom sensors and calibrated drive time remain explicit manual fallbacks because their identity/calibration cannot be inferred safely.

**Tech Stack:** Python 3.14, Home Assistant config flow, HA WebSocket API, vanilla JavaScript panel, pytest/pytest-homeassistant-custom-component, Playwright.

**Spec:** GitHub issue #8: https://github.com/denkz0ne/CCA_zaluzie/issues/8

## Global Constraints

- Preserve Home Assistant minimum version 2026.9.0.
- Preserve one controller per cover, all existing schedules and decision priorities, and cover orientation semantics.
- Never treat time-based estimated position as measured feedback.
- Never dispatch a motor command when automatic detection is unresolved.
- Preserve legacy explicit sensor and drive-time choices; legacy default `current_position` may enter automatic mode.
- Keep lamella/tilt control excluded.

## Review Focus

- Missing, unavailable, nonnumeric, boolean, out-of-range and NaN position attributes must not authorize movement.
- Conflicting valid `current_position` and `position` values must surface manual choice instead of guessing.
- Manual sensor and calibrated drive-time configurations must survive reload and options changes.
- Auto resolution must remain consistent across runtime, reset, dry-run and future prediction.
- Both native options and the side panel must hide/show the selector from the same resolution status.

---

### Task 1: Position source detector

**Files:** Create `custom_components/cca_zaluzie/position.py`; create `tests/test_position.py`.

**Interface:** `detect_position_source(attributes: Mapping[str, Any], tolerance: float) -> PositionSourceDetection`, with `source: str | None`, `reason: str | None`, and `automatic: bool`.

- [x] Write tests for canonical `current_position`, fallback `position`, conflicting values, invalid values and no feedback.
- [x] Run the new tests and confirm they fail because the detector is absent.
- [x] Implement the pure detector: only finite numeric values from 0 through 100 qualify; prefer `current_position`; if both valid values differ by more than tolerance, return unresolved/ambiguous; never infer a custom sensor or drive-time calibration.
- [x] Run `python -m pytest tests/test_position.py -q` and confirm all new tests pass.

### Task 2: Config defaults and native flow fallback

**Files:** Modify `custom_components/cca_zaluzie/config.py`, `config_flow.py`, `strings.json`, `translations/en.json`, `translations/sk.json`; modify `tests/test_config.py`, `tests/test_integration.py`.

**Interface:** Persist internal `position_source_auto: bool`; config creation sets it true and stores the detected source. If detection is unresolved, native setup presents the existing source selector and saves a manual selection. Options only include that selector when auto mode is unresolved; selecting it switches to manual mode.

- [ ] Add failing tests for auto defaults, legacy manual sensor/drive-time preservation, flow detection, failure fallback and options visibility.
- [ ] Run focused tests and confirm expected failures.
- [ ] Implement config normalization and native flow behavior, with localized failure reasons.
- [ ] Run focused config-flow tests and confirm they pass.

### Task 3: Consistent runtime, engine, operations and prediction

**Files:** Modify `controller.py`, `engine.py`, `operations.py`, `prediction.py`; extend `tests/test_engine.py`, `tests/test_integration.py`, and `tests/test_operations.py` or `tests/test_prediction.py` as needed.

**Interface:** `CoverController.position_source` exposes the resolved source or `None`; `snapshot()` exposes whether selection is automatic and its current resolution/reason.

- [ ] Add failing tests for auto fallback at runtime, unresolved-position movement inhibition, end-stop reset safety, and prediction using the same source.
- [ ] Run focused tests and confirm expected failures.
- [ ] Route every position-dependent decision through the effective source; unresolved automatic mode remains unavailable and cannot use an estimated drive time implicitly.
- [ ] Run focused tests and confirm they pass.

### Task 4: Side-panel selector visibility and explanation

**Files:** Modify `custom_components/cca_zaluzie/frontend/cca-zaluzie-panel.js`, translations/field metadata; extend `tests/browser/panel.spec.mjs`.

- [ ] Add browser checks that the selector is hidden on reliable auto resolution, appears with a reason on failure, and a manual change persists.
- [ ] Run the browser checks and confirm expected failures.
- [ ] Implement visibility and manual-mode switching using the controller's resolution status; keep unresolved auto mode from being saved as a manual value without user choice.
- [ ] Run browser checks and confirm they pass.

### Task 5: Documentation, release metadata and complete verification

**Files:** Modify `README.md`, `docs/INTEGRATION_BRIEF.md`, `docs/FEATURE_MATRIX.md`, `CHANGELOG.md`, and `custom_components/cca_zaluzie/manifest.json`.

- [ ] Document the detection order, failure fallback, manual choices and estimate-versus-measurement distinction.
- [ ] Bump the integration version and changelog according to the existing release convention.
- [ ] Run the full Python suite, browser suite, Ruff, hassfest and HACS validation; record exact results.
- [ ] Review the full diff and compatibility impact before PR, merge, release and issue closure.
