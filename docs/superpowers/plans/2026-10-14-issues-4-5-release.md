# CCA Žalúzie issues #4 and #5 release plan

## Approved scope

Deliver the full-integration discovery/Add-flow repair already in progress, then
implement the accepted requirements in issues #4 (per-cover motor-safe dry-run)
and #5 (read-only date-based prediction). Preserve the existing CCA decision
rules, config-entry/entity identity, support floor, and the explicit exclusion
of lamella tilt. Do not access Chrome or restart Home Assistant.

## Sequence and acceptance gates

### 1. Integration discovery and Add flow

- [x] Correct integration type from `helper` to `service`.
- [x] Correct Add button to HA's `/config/integrations/dashboard/add?domain=cca_zaluzie` route.
- [x] Add manifest and browser regression tests.
- [x] Verify all GitHub Tests and Validate jobs pass on the final change.

### 2. Dry-run (#4)

- [x] Add persistent per-entry simulation state, default off, retaining it through reload/restart.
- [x] Route every motor operation (including movement, timed drive, STOP, reset, cancellation and unload) through one dispatch gateway. In simulation it records `would_dispatch` and never calls HA cover services.
- [x] Keep physical observations/runtime separate from bounded virtual shadow state; do not claim physical completion or replay queued simulated work after disabling.
- [x] Keep native conditions read-only; suppress native actions and scripts in simulation unless their motor safety can be proven. Document the boundary clearly.
- [x] Expose an admin-only per-cover control and conspicuous overview status without reloading the entry.
- [x] Extend sanitized bounded trace and diagnostics, label simulated versus executed events, and cover failure, cancellation, unknown/unavailable inputs and multi-cover isolation.
- [x] Add regression tests asserting zero motor-service calls for all simulation paths.

### 3. Prediction (#5)

- [x] Implement a pure isolated prediction evaluator using the production rules, without modifying controller runtime, history, timers, HA storage, or calling services/actions/scripts.
- [x] Handle dates, timezone/DST, sun azimuth/elevation and 0/360 wrap, configured schedules and shading bounds, with uncertainty/conditional outcomes for future unknown sensors.
- [x] Add a read-only API by controller and date/range, computed-on-demand with bounded per-cover caching.
- [x] Add a compact prediction block in the selected cover's Overview with date selection, certainty labels, reasons, and no conflation with pending or executed events.
- [x] Test schedule and DST behavior, matching future forecasts, unknown/unavailable inputs, and zero side effects/state changes.

### 4. Documentation, release, and migration handoff

- [x] Update README, AGENTS, integration brief, feature matrix, UI docs, and changelog for the delivered behavior.
- [x] Run Python test matrix, Ruff, browser suite, hassfest, and HACS validation through GitHub Actions; address CI findings.
- [ ] Create and merge the pull request only after required checks are green; publish and verify the installable release archive and matching tag/manifest version.
- [ ] Stop at the release handoff so the user can update HACS/HA. After the user confirms update completion, perform the separately authorized one-time import of all four legacy CCA covers with dry-run enabled, report field mappings/unmapped fields, and verify no motor services were called.

## Safety properties

- Dry-run and prediction are separate. Prediction works whether dry-run is on or off.
- Dry-run is per cover; another controller remains unaffected.
- Turning dry-run off never dispatches stale work; only a new normal evaluation/recovery policy can act.
- No migration, real cover call, or HA restart occurs before release/update handoff.
