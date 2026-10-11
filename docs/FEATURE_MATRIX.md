# Feature mapping — 2026.10.0

Behavior reference: CCA 2026.10.04, upstream commit
`83e9925c3c0b1bbb96f6f55ef68c00e1c11870cf`. This is an independent implementation,
with Home Assistant's vertical position convention at the service boundary.

| Capability | Delivery | Implementation and evidence |
|---|---|---|
| One independent controller per cover, multiple entries | Implemented | Config flow, stable entities, separate storage; HA lifecycle tests |
| Blind, shutter, awning and sunshade; position orientation | Implemented | Validated type/target settings; config and regression tests |
| Position attribute, selected sensor, calibrated drive time and tolerance | Implemented | Controller feedback adapter and motor operations; feedback and timed-motion tests |
| Morning/evening Early/Late, today/tomorrow workdays, calendar | Implemented | Engine schedule windows and calendar start/end matching; engine and schedule tests |
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

Copying settings between covers and a no-movement evaluation mode are proposals
for a later version. They are not included in this release.
