# Issue #13 control-engine implementation plan

**Goal:** Implement the user-approved state/priority simplification in issue #13 with backwards-compatible migration, integration and browser coverage, and release it through GitHub CI.

**Base:** `2026.12.1` (`f682750`). **Branch:** `feat/issue-13-control-engine`.

**Source decisions:** `docs/superpowers/specs/2026-10-16-issue-13-decisions.md` and issue #13. User-selected answers are recorded there; unanswered behavior is preserved conservatively.

## Task 1 — Decision model and persistent state

- Add focused failing tests for persisted phase/correction/latch state, old runtime restoration, and idempotent reevaluation.
- Introduce typed, per-cover state for active phase and generation, base/effective target, correction start/deadline, passage lockout and completed/deferred daily intents.
- Keep runtime storage backward compatible; default missing fields without changing cover identity or issuing movement during migration.
- Make decision output expose winner, suppressed candidates, inhibit, next action and certainty without adding a second evaluator.

## Task 2 — Contact and Force safety

- Test open/closed/unknown/unavailable contact behavior, rapid opening response intent, post-close timer rearming, and the scoped Force-close exception.
- Consolidate generic binary contact behavior while retaining old `window_open`/tilt configuration keys as migration aliases until safe normalization is verified.
- Ensure passage lockout takes priority over Force-close only when that cover's lockout is enabled; unknown/unavailable blocks dangerous close. Preserve legacy Force precedence for other conflicts and compatibility entities.
- Keep the current non-lockout ventilation behavior for ordinary contacts.

## Task 3 — Exclusive ventilation/shading phases and weather stability

- Add failing transition tests: active ventilation completes before shading starts, and active shading completes before ventilation starts; no combined target is emitted.
- Remove the old overlap policy from effective decisions after migration, retaining stored legacy keys as compatibility data where needed.
- Apply asymmetric internal weather stabilization based on the complete user-selected weather-state set. Transitions between selected states must not disable shading.
- Keep all supported weather values selectable and unknown inputs conservative.

## Task 4 — Daily schedule, morning coalescing, and correction sessions

- Add tests for Early/Late plus sun thresholds, workday/weekend, DST/local timezone, correction ±20 p.p./120 s, and new phase invalidation.
- Remove morning/evening lux and calendar from new schedule decisions only after migrated values are recognized and diagnostics explain retired behavior; retain optional shading lux.
- Implement internal 30-minute confirmed-event lookahead: logically fulfill morning when a confirmed opposite shading movement is near; preserve the original event in history as merged/deferred. Never skip the guaranteed morning intent based only on uncertain forecast or unknown inputs.
- Do not expose new internal timers as options.

## Task 5 — One-shot phase actions and compatibility

- Test start/end one-shot latches, repeated evaluation, reset on next valid phase/day, and safety/legacy Force entities.
- Add explicit command actions using existing config/API patterns; they mark a phase boundary once rather than permanently pinning the cover target.
- Preserve legacy Force entities and their current meaning. Contact safety continues to inhibit an unsafe Force-close in the scoped passage-lockout case.

## Task 6 — Shared overview, prediction, dry-run and panel

- Test that live decision, next-action prediction and dry-run use the same arbitration while prediction remains read-only and simulation never calls services.
- Expose concise phase/target/owner/inhibit/correction/lockout/next-action details through existing controller snapshots and history.
- Update the production overview and configuration progressively, keep unsafe/advanced legacy options accessible during migration, and explain deferred/merged movement in plain Slovak.

## Task 7 — Migration, docs and end-to-end compatibility

- Add config/runtime migration tests from current and older storage formats, preserving every entry/entity ID and configured value.
- Update feature matrix, issue acceptance mapping, user docs and release notes. Keep an explicit old-to-new field map and document behavior no longer used in scheduling.
- Run Python, browser, Ruff, hassfest and HACS checks; fix regressions; request independent read-only review; open PR, wait for passing GitHub CI, merge, tag the next patch and verify the GitHub release archive.
- Do not access or restart live Home Assistant or operate motors.

