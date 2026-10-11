# CCA Žalúzie release design

The binding product requirements are INTEGRATION_BRIEF.md, CCA_REFERENCE.md,
AGENTS.md and docs/ui/README.md. The user authorized implementation through the
published final release on 2026-10-11 and confirmed continued execution.

## Architecture

One config entry owns exactly one cover and one controller. Integration setup
registers one sidebar panel and authenticated WebSocket API shared by entries.
Each controller owns serialized service dispatch, timer/state subscriptions,
versioned persistent runtime state and bounded event history. Pure Python
configuration and decision modules have no Home Assistant dependencies.

Use Home Assistant 2026.10.0 as the support floor, Python 3.14 for HA integration
tests, probatio for the current HA schema interface, standard entity selectors,
config/options flows, HA storage, service contexts and diagnostics. Do not copy
CCA YAML or Entity Controller source. Link and attribute behavioral references.
The upstream CCA reference remains 83e9925 (2026.10.04), verified today.

## Behavior

Track observed position, desired target, winning mode/reason, dispatch inhibition,
pending condition deadlines, manual protection, scheduled event adoption and
command completion separately. Evaluate schedules/light/sun, shading, contacts,
resident, manual and force layers on every relevant event and timer boundary.
Force wins target arbitration. Pause inhibits all dispatch, including Force.
Disabled/unavailable inputs never authorize movement. Preserve the underlying
target while inhibited. Actions and conditions use Home Assistant's native engine.

Morning/evening use workday/non-workday Early/Late bounds, optional calendar
events, sensor AND/OR, stable duration/hysteresis and per-day adoption. Sensor-only
mode has no Late fallback. Shading has independent start/end AND/OR predicates,
geometry, lux, two temperatures, weather/forecast/custom input, alternate target,
confirmation and maximum retry windows. Unknown required inputs block decisions.
Ventilation contacts are ignored when ventilation is disabled. Otherwise debounce,
separate full/tilted contact policies and transition conditions apply. Manual
policies independently protect actions and can reset by time, duration or dwell.
Force recovery and startup/outage recovery are configurable and observable.

Cover types retain CCA vertical target semantics; default open/closed targets are
100/0, or 0/100 for awning. No lamella angle, tilt actuator services or tilt bands.
No-position devices use explicit drive-time handling with stop and observability;
never claim observed position from an estimate.

Reset owns the cover command lock. Full close is followed by confirmed lower-end
arrival (position feedback or explicit calibrated drive time), exactly 60 seconds
dwell, then STOP. Stop is attempted on cancel/unload. Unavailability, service
failure and restart interrupt the operation; interrupted state is persisted and
never silently resumed. Recompute after completion/cancel without erasing layers.

## UI and configuration

Adapt the approved HTML layout: persistent cover list, compact per-cover overview
and grouped configuration, drafts per cover, Save/Discard, contextual help and
individual manual block checkboxes. Use actual HA state via authenticated API.
Timeline distinguishes planned, pending, executed, blocked, cancelled and failed
events. An event opens its condition and command details. Controls show real errors.
All inputs are validated on the server; admin permission is required for writes.
Advanced native condition/action selectors retain CCA customization semantics.

## Release acceptance

Feature matrix must list every upstream input group and explicit tilt exclusions.
Tests cover priorities, thresholds, timing, restart, unknown states, duplicate
dispatch, context/manual detection, reset failure/cancel and stable entry identity.
Run actual HA lifecycle/config/WS/service tests and browser tests for production
panel drafts, errors and cover switching. GitHub Tests, hassfest and HACS validation
must pass on the merge commit before a release is published. Release archive must
contain the installable component, match manifest version and support HACS custom
repository installation. Do not imply physical hardware validation without it.

## Proposals awaiting discussion

Copy settings between covers and a no-movement evaluation mode remain proposals;
they are not part of the authorized first release scope.
