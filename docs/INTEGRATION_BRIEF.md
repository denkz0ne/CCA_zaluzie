# Integration implementation brief

Status: requirements and architecture brief only; no integration code exists yet.

## User goal

Create a Home Assistant custom integration that manages multiple blinds/shutters from one config-flow-driven integration and presents a polished per-cover control dashboard. The behavioral reference is the latest upstream Cover Control Automation (CCA). The visual and functional layout reference is the user's **Svetlo v tme** / **Entity Controller (EC)** integration. This is not an instruction to clone either project's code.

## Confirmed from user

- The new project/repository is named **CCA_zaluzie**.
- The new integration manages configured covers according to user-defined schedules and behavior.
- The interface should follow the same general principle as EC: covers grouped into controllers/rooms, a timeline of events, and visible current state, blocks, manual states and controls.
- Feature concepts explicitly named: shading, morning/evening control, blocking, manual states, and settings per configuration.
- The integration should have a similar config flow to EC.
- CCA is the behavior source to study. Latest checked snapshot: upstream version 2026.10.04, commit 83e9925.

## UI and operating model

### Main view
Use EC's compact controller overview as the interaction model:
- One controller/card per configured cover (or optional named group/controller containing covers).
- Show cover name, current position and tilt when available, availability, active/disabled status, current desired mode/target, next event and concise reason/status.
- Show key actions without opening settings: open, close, stop, set shading/ventilation target, pause/enable automation, clear override, run/resync if allowed.
- Use a timeline covering a configurable period, default conceptually 24 hours, with distinct event types: scheduled morning opening, evening close, sun shading start/end, ventilation, forced state, lockout, manual override, blocked action and recovery. Mark actual vs planned events separately.
- Provide clear state distinctions: waiting for time window, waiting for sensor, pending confirmation/delay, moving, active shading, manual override, force active, blocked by contact, paused, unavailable, disabled and idle.
- A timeline event should be inspectable and say *why* it is scheduled, delayed, blocked, cancelled or executed.
- EC's current overview presents controller state/status text, room/controller toggles, edit settings, per-entity state controls and a 24-hour state history. Reuse that information hierarchy and legibility, adapted to cover entities and a richer event timeline.
- Provide an individual detail view with full timeline, current target arbitration, source sensor values, last decision and diagnostics.
- Avoid turning the overview into a wall of 100 settings. Separate everyday controls from advanced conditions.

### Config flow (proposed progressive sections)
1. Create named controller/cover entry; select one or more `cover` entities (MVP may start with one cover per controller but data model should support multiple).
2. Basic schedule: morning open, evening close, weekdays/weekends, optional workday/calendar support.
3. Cover calibration: cover type, open/closed mapping if entity semantics require it, preferred open/close/shading/ventilation targets, position/tilt availability and tolerances.
4. Select optional behaviors: sun shading, sensor-based open/close, ventilation/window contacts, resident/sleep mode, manual override policy, force/pause controls.
5. Configure only the fields relevant to selected behaviors; advanced conditions can be tucked away.
6. Preview/validate schedule and conflicts; finish with a controller dashboard.
7. Options flow edits settings later without destroying runtime history. Reconfigure should preserve config entry and entities where possible.

## Runtime behavior requirements

### Desired-target arbitration
Treat each cover's current physical state and desired target as different data. Recompute target deterministically from current configuration and HA state, with a user-readable winning reason and suppressed lower-priority reasons. Start with an explicit priority model:
1. integration disabled/unavailable safety handling;
2. Force target (highest requested target);
3. force pause/movement inhibition (blocks movement, retains target/state);
4. manual override policy;
5. open-window/tilted-window lockout;
6. ventilation target;
7. sun-shading target;
8. morning/evening schedule and resident constraints;
9. neutral/idle target.

CCA states Force outranks window lockout and manual override; pause is a final dispatch inhibit that does not discard target. Decide and document exact precedence for pause vs emergency Force in our design. Do not implement conflicting precedence implicitly through trigger ordering.

### Idempotence and lifecycle
- Evaluate triggers and scheduled boundaries, but route every decision through one per-cover state machine / coordinator.
- Before sending a service call, check availability, current position/tilt, tolerance, active motion and inhibit reasons.
- Distinguish desired target from actual position and command lifecycle.
- Debounce noisy sensors and use hysteresis to avoid repeated moves.
- For delayed shading, record a pending decision; after delay, re-evaluate all conditions. Cancel/reset pending when conditions fail.
- Avoid duplicate simultaneous service calls. Persist state needed for restart recovery; on HA reload/startup reconcile with current cover/sensors.
- Never treat an integration-originated position report as a user manual override. Correlate command context and observed changes.
- Provide configurable recovery policy; never surprise-move a cover on startup without a safe, explicit and observable policy.
- Explain all blocked/suppressed decisions in UI and logs.

### Entities / controls (initial direction)
Each controller could expose:
- a control/select entity for operating mode (automatic, paused, manual/force modes);
- binary sensors for shading, manual override, window lockout, force pause, availability/fault as applicable;
- sensors for current desired action, next planned event, last decision/reason, schedule window and runtime status;
- buttons for clear override / reconcile if appropriate.
Do not create entity clutter without a user action. Prefer device grouping and entity categories.

### Persistence and migration
The integration should own its config and state; do not require per-cover `input_text` helpers as CCA does. Store durable settings in config entry/options and only persist state needed for correctness/history. Keep event history bounded, timezone-aware and resilient to restarts. Version the stored schema and implement migration if it changes.

### Safety / edge cases to design before coding
- Cover unavailable during trigger or returns after missed schedule.
- Home Assistant restart while a shading confirmation delay or movement is pending.
- Sunset/sunrise and DST clock changes; missed or repeated local time.
- Conflicting workday/calendar schedule, resident sensor, manual override, force, pause and window contacts.
- Unknown/unavailable sensor values: never coerce unknown to a passing threshold.
- Device with no position, inverted position, tilt unsupported, or command service that is slow/optimistic.
- Manual change while a scheduled timer is pending.
- Multiple covers sharing a motor group; staggered start and partial failures.
- Integration reload/removal and config entry migration without orphaned entities.
- Repeated sensor jitter, duplicate events and action failure.

## MVP recommendation (to be reviewed before implementation)

1. Config flow, controller data model, entity selection and basic per-cover settings.
2. Morning/evening schedules with weekday/weekend times and explicit early/late behavior.
3. Per-cover automation enable, pause, simple manual override detection/reset.
4. Shading by sun geometry plus optional brightness; pending wait/recheck; shading end/hysteresis.
5. Overview card/list and 24-hour event timeline with explainable states and manual controls.
6. Persistent config, HA restart reconciliation, diagnostics/logbook.
7. Add ventilation contacts, temperature/weather forecasts, calendar, resident mode, force controls, dynamic shading tilt, custom actions and recovery refinements in later stages.

This MVP is a recommendation, not an approved feature cut. Do not silently drop CCA behaviors from the long-term target; track deferred features in issues or `docs/FEATURE_MATRIX.md`.

## Agent instructions

Before changing code, read:
1. this file;
2. [CCA_REFERENCE.md](CCA_REFERENCE.md);
3. repository `AGENTS.md`;
4. current upstream source and docs if behavior is being implemented (upstream main can change).

Keep feature decisions traceable to one of: user-confirmed requirement, CCA observed behavior, EC layout precedent, or explicitly labeled proposal. Do not present proposals as decisions. For substantial runtime behavior, write tests around priorities, timing, unavailable values, restarts and duplicate triggers before coding.
