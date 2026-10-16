# Feature mapping — 2026.12.2

Behavior reference: CCA 2026.10.04, upstream commit
`83e9925c3c0b1bbb96f6f55ef68c00e1c11870cf`. This is an independent implementation,
with Home Assistant's vertical position convention at the service boundary.

| Capability | Delivery | Implementation and evidence |
|---|---|---|
| One independent controller per cover, multiple entries | Implemented | Config flow, stable entities, separate storage; HA lifecycle tests |
| Blind, shutter, awning and sunshade; position orientation | Implemented | Validated type/target settings; config and regression tests |
| Automatic measured-position detection with manual fallback, selected sensor, calibrated drive time and tolerance | Implemented | Prefers valid `current_position`, falls back to valid `position`, exposes manual choice on ambiguity/unavailability, blocks unresolved movement; detector, HA lifecycle, motor and browser tests |
| Morning/evening Early/Late, today/tomorrow workdays | Implemented | Engine schedule windows and solar thresholds; retired morning/evening brightness and calendar matching are migrated out of active scheduling |
| Brightness/sun elevation, stable duration, AND/OR, hysteresis, once per day | Implemented | Separate logical schedule ownership and dispatch; engine and schedule tests |
| Whole-cover partial-height shading | Implemented | Shading target plus alternate trigger/target; engine tests |
| Shading geometry, brightness, two temperatures, forecast/weather/custom input | Implemented | Separate start/end predicates, optional AND/OR groups and independent hot-temperature policy; engine tests |
| Shading confirmation, cancel/recheck, retry ceilings, immediate geometry end | Implemented | Persisted pending lifecycle and end-action ownership; shading retry tests |
| Full-open/tilted contacts, lockout and ventilation policies | Implemented | Debounce, full/partial targets, start/end conditions and return policies; engine tests |
| Resident sleep/awake behavior | Implemented | Opening inhibition and configured closing/wake policies; engine and schedule tests |
| Manual detection, blocking, adoption, reset/return rules | Implemented | Context correlation, configured position sensor, manual engine state; HA and engine tests |
| Force targets and pause | Implemented | Latest activated Force wins; pause is a final dispatch inhibit; regression tests |
| Native conditions, before/after/custom actions, drive delay and instance guards | Implemented | HA validation/Script compilation, candidate target variables, serialized dispatch rechecks; HA tests |
| Startup/outage reconciliation | Implemented | Explicit policy, off by default; interrupted operations never resume silently; HA lifecycle tests |
| Per-cover full-close reset, exactly 60 seconds dwell, STOP | Implemented | Exclusive motor operation, monotonic dwell, endpoint monitoring, cancellation and external-command interruption; reset guard and HA tests |
| Configuration/history persistence and migration | Implemented | HA storage and options reload retain identity/history; HA tests |
| Live sidebar controls, per-cover drafts and settings | Implemented | Production JS/CSS with admin WebSocket API; browser and HA API tests |
| Timeline, pending/next event, decision inputs, debug and diagnostics | Implemented | Bounded history, inspectable event details, sanitized diagnostics; browser/HA tests |
| Full integration discovery and Add flow | Implemented | `integration_type: service`; native dashboard Add route; manifest and browser regression tests |
| Per-cover dry-run without motor calls | Implemented | Persistent isolated simulation runtime, single motor dispatch gateway, timed shadow position, suppressed native actions and visible panel state; HA and browser tests |
| Read-only date prediction | Implemented | Production engine on copied state, local date/DST solar geometry, provider forecasts, certainty and assumptions; API and browser tests |
| Mode correction, exclusive shading/ventilation, phase actions and morning movement merge | Implemented | Internal ±20 percentage-point / 120-second correction session, serialized active phases, confirmed 30-minute morning merge and one-shot phase controls; engine and browser tests |
| Selected-weather stabilization and Force/contact safety | Implemented | Internal asymmetric confirmation based on each cover's selected states; enabled passage lockout prevents Force-close on open or unknown contact; regression tests |
| Blueprint input_text helper and automation traces | Replaced | Integration-owned storage and structured event/condition history |
| Lamella actuator tilt, tilt bands/waits/reposition | Excluded by user | No tilt service or tilt target is sent; tilted-window contact remains supported |

## Verification boundary

GitHub Actions runs the actual HA setup, options, lifecycle, service and API tests
on Linux, plus production-panel browser tests, hassfest and HACS validation.
Pure engine/motor tests also run locally. Motor responses are simulated in these
tests; the user's installed Home Assistant and physical motors have not been
modified or used to validate movement. Device-specific feedback, full drive time
and end-stop behavior must be checked after installation before enabling automation.

## Proposals awaiting discussion

Copying settings between covers remains a proposal for a later version. It is not
included in this release.
