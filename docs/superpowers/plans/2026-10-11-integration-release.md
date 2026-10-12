# CCA Žalúzie Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the documented CCA Žalúzie integration and publish its verified release.

**Architecture:** Pure configuration/decision modules feed an independent HA controller per cover. The controller serializes motor commands and persists state/history; HA entities and an authenticated custom panel expose the same controller.

**Tech Stack:** Python 3.14, Home Assistant 2026.9+, probatio, pytest, native JavaScript, Playwright, GitHub Actions, HACS.

**Spec:** ../specs/2026-10-11-integration-design.md

## Global Constraints

- Exactly one cover per config entry/controller and panel row.
- Preserve applicable CCA behavior; exclude only actuator lamella/tilt control.
- Home Assistant 2026.9.0 minimum; no integration runtime pip dependencies. Initial 2026.10.0 floor was revised after verifying 2026.9 compatibility.
- Reset must confirm lower-end arrival, dwell 60 seconds, then STOP.
- Never resume interrupted reset on restart; pause inhibits Force dispatch too.
- Slovak UI labels, stable entry/entity identity, config-flow setup, bounded history.
- Do not change user infrastructure or restart the user's Home Assistant.

## Review Focus

- DST ambiguous/nonexistent boundaries must not duplicate daily motor commands.
- Sensor unknown during pending shading must cancel the unsafe pending transition.
- Options update during reset must interrupt safely and preserve history.
- Untrusted panel input must not bypass admin checks or configuration validation.
- Device feedback without an inherited context must not create false manual overrides.

### Task 1: Configuration and behavioral engine

**Files:** Create custom_components/cca_zaluzie/{const,config,model,engine}.py, tests/test_engine.py, tests/test_config.py.

**Interfaces:** `validate_config(dict) -> dict`, `evaluate(config, runtime, snapshot, now) -> Decision`; Reading/Snapshot/Runtime/Decision in model.py. Runtime is JSON serializable through explicit to_dict/from_dict methods.

- [ ] Write failing tests for validation, workday Early/Late, sensor-only mode, AND/OR, unknown values, shaded start/end delays, hysteresis, contacts, force/pause, manual protection/reset, resident, alternate/inverted targets, stable durations, retry ceilings and DST.
- [ ] Run `python -m pytest tests/test_config.py tests/test_engine.py -q`; expected missing feature failures.
- [ ] Implement configuration field metadata and deterministic layer evaluation. Include a predicate trace and next deadline in Decision.
- [ ] Run the tests; expect all green. Commit the engine slice.

### Task 2: HA lifecycle, command and reset controller

**Files:** Create component __init__.py, controller.py, config_flow.py, entity.py, sensor.py, switch.py, button.py, diagnostics.py, services.yaml and translations; tests/test_controller.py and tests/test_integration.py.

**Interfaces:** `CoverController.async_evaluate()`, `.async_control(action, position=None)`, `.async_reset()`, `.async_cancel_reset()`, `.snapshot()`; entry.runtime_data owns controller.

- [ ] Write failing HA tests for creation/duplicate/options reload, context correlation, idempotent commands, unknown states, unavailable recovery, service failure, no-position movement timeout, reset arrival/dwell/STOP, restart interruption and option updates during reset.
- [ ] Run the tests against real HA fixtures and inspect failures.
- [ ] Implement listeners, timers, native conditions/actions, persistence, serialized dispatch and entity platforms; preserve entity IDs across reloads.
- [ ] Run all Python tests; expect green. Commit the runtime slice.

### Task 3: Authenticated API and production panel

**Files:** Create api.py, frontend/cca-zaluzie-panel.js, tests/test_api.py, tests/browser/panel.spec.mjs, browser demo fixture and package.json.

**Interfaces:** WebSocket list/get/configure/control/subscribe handlers; payload includes entry_id, state, config fields, events and decisions. Admin validation applies to all writes.

- [ ] Write failing API and browser tests for permission checks, invalid settings, persistent drafts per cover, Save/Discard, status controls, error reporting, detail timeline and reset progress.
- [ ] Implement panel registration/static path, unsubscribe on disconnect, real controller payload and approved compact Slovak interface.
- [ ] Run Python and Playwright suites; expect green. Visually inspect production panel in a browser.
- [ ] Commit the UI slice.

### Task 4: Completeness, review and release

**Files:** Update README.md and docs; create FEATURE_MATRIX.md, CHANGELOG.md, attribution/license, hacs.json, workflows/{tests,validate,release}.yaml and packaging script.

**Interfaces:** GitHub workflows validate the actual component and release a reproducible archive with manifest version matching tag.

- [ ] Audit all upstream input groups against implementation and tests, close any unexplained gaps.
- [ ] Run all suites, lint, HA lifecycle and browser checks; fix material findings.
- [ ] Obtain a fresh whole-branch code review, address findings with regression tests.
- [ ] Push the branch, create/attach PR, wait for Tests/hassfest/HACS checks, merge after green.
- [ ] Confirm main checks pass, publish release 2026.10.0 with installable archive and verify tag, assets and HACS metadata.
