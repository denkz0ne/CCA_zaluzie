# Integration implementation brief

Status: implemented and released as version 2026.12.7 for Home Assistant 2026.9+. This document preserves
the original requirements; current delivery mapping is in [FEATURE_MATRIX.md](FEATURE_MATRIX.md).

## 2026.11.0 runtime additions

- Home Assistant discovers CCA Žalúzie as a full service integration and the panel's Add action
  opens its native setup flow.
- A persistent per-cover dry-run mode uses the normal evaluator and live HA inputs while routing
  every motor command through a no-call gateway. It stores a separate simulated runtime and
  interpolated shadow position; native actions/scripts are recorded as suppressed. Disabling
  simulation never replays a virtual command.
- Overview prediction evaluates copied state with the production engine for a selected local date
  and a 1–7 day horizon. It reads matching future provider forecasts when available and labels
  uncertain future inputs. The endpoint performs no service calls or persistent/runtime writes.

## 2026.11.1 automatic position feedback

- New covers automatically prefer a finite numeric `current_position` in the
  0–100 range, then use a valid `position` attribute when the standard value is
  absent or invalid.
- If both attributes are valid but differ beyond the configured tolerance, or
  neither yields live feedback, the setup/options flow and side panel expose the
  source selector with the reason. An unresolved source blocks movement and
  end-stop reset.
- Explicit custom-sensor and calibrated drive-time configurations remain
  manual. A timed estimate remains distinct from measured device feedback.

## 2026.12.0 panel redesign

- The approved HA-style panel adds explicit top-edge drag grips, durable ordering,
  observed last-movement direction and stable selection/drafts through reloads.
- Selective multi-cover configuration validates all candidates and revisions before
  writing. Names, entities, physical targets/calibration and native editors remain individual.
- Overview prediction is replaced by measured history with Recorder fallback and gaps;
  simulation controls move into configuration. The read-only prediction API remains available.
- Next actions describe conditional timing and manual deferral without changing the
  evaluator or enabling automatic return when the user disabled it.
- See [panel operation](PANEL.md) and the approved UI specification for details.

## 2026.12.1 calculated next movement

- The overview predicts the next movement from the current time and live runtime,
  using the production decision engine and calculated solar position.
- It compares current sensor and condition values with values in the movement
  scenario, including solar azimuth, elevation and configured sun threshold.
- Future inputs that cannot be known remain explicit assumptions; the scenario
  does not promise a time when live sensor values may change.
- The calculation is read-only and preserves manual protection and controller
  runtime. Measured position history remains available beside the prediction.

## 2026.12.2–2026.12.3 approved issue #13 behavior

- Active shading and ventilation do not overlap; an active phase finishes before
  the other can take over. The overview provides one-shot start/end actions.
- A confirmed shading start within 30 minutes may fulfill the morning opening
  logically, avoiding an immediate opposite-direction motor movement.
- Small user corrections are measured from the original mode target. The limit is
  ±20 percentage points and the fixed edit window is 120 seconds from the first edit.
- An enabled open-contact lockout blocks Force-close when the contact is open or
  unknown. Other Force priority and existing Force entities remain supported.
- Opening a passage contact uses at most two seconds of confirmation regardless
  of older configurable delays; closing keeps the configured stable confirmation.
  With lockout enabled, verified closure starts a persisted 30-minute hold against
  downward movement. Reopening clears and rearms it.
- The hold expires automatically and appears as the planned next close. The
  overview's explicit Close action can end it once, only with a currently stable
  closed contact. Other downward controls, Force-close, unknown and unavailable
  contact cannot bypass it. Lockout-off contacts do not start this hold.
- An ordinary open contact cannot replace an already active shading phase.
  Shading and ventilation remain serialized; the safety lockout can still override.
- Weather changes are stabilized internally according to each cover's selected
  states. Morning/evening brightness and calendar inputs no longer affect the
  schedule; legacy entry values are migrated, and a legacy brightness sensor can
  remain as the optional shading sensor.

## User goal

Create a Home Assistant custom integration that manages multiple blinds/shutters from one config-flow-driven integration and presents a polished per-cover control dashboard. The behavioral reference is the latest upstream Cover Control Automation (CCA). The visual and functional layout reference is the user's **Svetlo v tme** / **Entity Controller (EC)** integration. This is not an instruction to clone either project's code.

## Confirmed from user

- The new project/repository is named **CCA_zaluzie**.
- The new integration manages configured covers according to user-defined schedules and behavior.
- The interface should follow the same general principle as EC: covers grouped into controllers/rooms, a timeline of events, and visible current state, blocks, manual states and controls.
- Preserve the original CCA logic and its layered conditions/controls, expanding blueprint architecture limits where useful.
- The user's current hardware is ordinary blinds that move up/down. The confirmed exclusions are lamella/tilt movement and, from 2026.12.6, tilted-window contact sensing and behavior; shading by moving the whole blind to a partial-height position remains required. Preserve all other CCA cover-type semantics as applicable.
- Feature concepts explicitly named: shading, morning/evening control, blocking, manual states, strong debug/states/logs/timelines, and settings per configuration.
- Simplify configuration through progressive disclosure and conditional fields without deleting applicable CCA behavior.
- The integration should have a similar config flow to EC.
- CCA is the behavior source to study. Latest checked snapshot: upstream version 2026.10.04, commit 83e9925.

## UI and operating model

### Main view
Use EC's compact controller overview as the interaction model:
- Exactly one automation/controller per cover and exactly one row/card per cover in the side panel, following Entity Controller's per-controller row pattern. Do not group multiple independently controlled covers into a single automation row; shared defaults may be applied during setup, but runtime state, controls, logs, timeline and reset action remain per cover.
- Show cover name, current vertical position when available, availability, active/disabled status, current desired mode/target, next event and concise reason/status.
- Show key actions without opening settings: open, close, stop, set shading/ventilation target, pause/enable automation, clear override, reset position, run/resync if allowed.
- Use a timeline covering a configurable period, default conceptually 24 hours, with distinct event types: scheduled morning opening, evening close, sun shading start/end, ventilation, forced state, lockout, manual override, blocked action and recovery. Mark actual vs planned events separately.
- Provide clear state distinctions: waiting for time window, waiting for sensor, pending confirmation/delay, moving, active shading, manual override, force active, blocked by contact, paused, position reset in progress, unavailable, disabled and idle.
- A timeline event should be inspectable and say *why* it is scheduled, delayed, blocked, cancelled or executed.
- EC's current overview presents controller state/status text, room/controller toggles, edit settings, per-entity state controls and a 24-hour state history. Reuse that information hierarchy and legibility, adapted to cover entities and a richer event timeline.
- Provide an individual detail view with full timeline, current target arbitration, source sensor values, last decision and diagnostics.
- Avoid turning the overview into a wall of 100 settings. Separate everyday controls from advanced conditions.

### Config flow (proposed progressive sections)
1. Create one named automation/controller entry for exactly one `cover` entity. The integration supports multiple covers by creating multiple independent entries, each with its own side-panel row and runtime state. Shared defaults may be offered as setup templates, but not as a combined multi-cover automation.
2. Basic schedule: morning open, evening close, weekdays/weekends, optional workday/calendar support.
3. Cover calibration: select ordinary vertical cover, confirm direction/position source, configure open/close/shading/ventilation targets, position feedback and tolerance. Do not offer tilt/lamella settings.
4. Select optional behaviors: sun shading, sensor-based open/close, ventilation/window contacts, resident/sleep mode, manual override policy, force/pause controls. Keep all applicable CCA behavior available; omit tilt/lamella controls and tilted-window contacts.
5. Configure only the fields relevant to selected behaviors; advanced conditions can be tucked away.
6. Preview/validate schedule and conflicts; finish with a controller dashboard.
7. Options flow edits settings later without destroying runtime history. Reconfigure should preserve config entry and entities where possible.

## Runtime behavior requirements

### Per-cover position reset (end-stop calibration)

Each cover row must offer a manual **Reset position** action. This is a deliberate calibration cycle for covers whose reported position has drifted or is no longer trustworthy:
1. Start by commanding that cover fully down/closed.
2. Keep the cover at the lower end stop for **60 seconds**.
3. Send a stop command.
4. Only after the sequence succeeds, mark the cover's position as reset/calibrated and record a completion event.

Requirements: run independently per cover; show a visible countdown/progress state and timestamp in its row and timeline; reject a second reset while one is active; allow a safe cancel; do not allow schedule/shading/ventilation/manual service commands to race this sequence; preserve schedule/force/override state and recompute the desired target after completion or cancellation. On unavailable cover, failed close/stop service, HA restart, or interrupted sequence, mark reset as failed/interrupted and do not claim calibration succeeded. Persist enough operation state to report interruption after restart; require an explicit retry rather than silently restarting motor movement. Make the 60-second dwell configurable only if later requested; initial behavior is exactly one minute.

The calibration command is explicitly a full-close movement followed by a one-minute bottom-end-stop dwell and stop. Do not replace it with a software-only position assignment or a generic `cover.set_cover_position` assumption unless the selected device/service semantics have been validated.

### Desired-target arbitration
Treat each cover's current physical state and desired target as different data. Recompute target deterministically from current configuration and HA state, with a user-readable winning reason and suppressed lower-priority reasons. Start with an explicit priority model:
1. integration disabled/unavailable safety handling;
2. Force target (highest requested target);
3. force pause/movement inhibition (blocks movement, retains target/state);
4. manual override policy;
5. ordinary open-window passage protection;
6. ventilation target;
7. sun-shading target;
8. morning/evening schedule and resident constraints;
9. neutral/idle target.

CCA states Force outranks window lockout and manual override; pause is a final dispatch inhibit that does not discard target. Decide and document exact precedence for pause vs emergency Force in our design. Do not implement conflicting precedence implicitly through trigger ordering.

### Idempotence and lifecycle
- Evaluate triggers and scheduled boundaries, but route every decision through one per-cover state machine / coordinator.
- Before sending a service call, check availability, current vertical position, tolerance, active motion and inhibit reasons.
- Distinguish desired target from actual position and command lifecycle.
- Debounce noisy sensors and use hysteresis to avoid repeated moves.
- For delayed shading, record a pending decision; after delay, re-evaluate all conditions. Cancel/reset pending when conditions fail.
- Avoid duplicate simultaneous service calls. Persist state needed for restart recovery; on HA reload/startup reconcile with current cover/sensors.
- Never treat an integration-originated position report as a user manual override. Correlate command context and observed changes.
- Provide configurable recovery policy; never surprise-move a cover on startup without a safe, explicit and observable policy.
- Explain all blocked/suppressed decisions in UI and logs.

### Entities / controls (initial direction)
Each per-cover automation/controller could expose:
- a control/select entity for operating mode (automatic, paused, manual/force modes);
- binary sensors for shading, manual override, window lockout, force pause, availability/fault as applicable;
- sensors for current desired action, next planned event, last decision/reason, schedule window and runtime status;
- buttons for clear override / reconcile and per-cover position reset.
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

## Delivery approach

Deliver in vertical slices, but the target remains behavioral parity with all applicable CCA logic. Keep a feature matrix that marks each branch as implemented, in progress, deferred or explicitly excluded. The confirmed exclusions are lamella/tilt behavior and tilted-window contacts; shading via partial vertical position is included. A first usable slice can provide the config flow, multi-cover model, basic schedule, manual override/pause, and timeline/debug foundation; subsequent slices add CCA condition groups, shading, ventilation, resident/calendar, force/recovery/actions, and full diagnostics. This is sequencing only, not a feature cut. Do not label the first slice “CCA parity.”

## Agent instructions

Before changing code, read:
1. this file;
2. [CCA_REFERENCE.md](CCA_REFERENCE.md);
3. repository `AGENTS.md`;
4. current upstream source and docs if behavior is being implemented (upstream main can change).

Keep feature decisions traceable to one of: user-confirmed requirement, CCA observed behavior, EC layout precedent, or explicitly labeled proposal. Do not present proposals as decisions. For substantial runtime behavior, write tests around priorities, timing, unavailable values, restarts and duplicate triggers before coding.

## Scope clarification: CCA limits and simplified setup

- Preserve every CCA behavior and its layered condition logic except lamella/tilt control and tilted-window contacts. Do not cut the project down to the initial “basic” feature slice.
- Expand implementation limits caused by the blueprint model: multiple covers managed under the integration, integration-owned state (no 254-character helper per cover), central/shared configuration with per-cover overrides, richer persisted history and integration-native UI/diagnostics.
- Retain behavioral safeguards that are useful: early/late schedule boundaries, trigger dwell/wait times, hysteresis, retry ceilings, position tolerance, lockout, and explicit recovery policy.
- Simplify the user task, not the behavior: presets, sensible defaults, conditional fields, grouped advanced sections, validation and a preview. Users should not need to understand 100 YAML selector IDs to configure one blind.
- Exclude tilted-window sensing/behavior and lamella angle/tilt functionality (including tilt shading bands and tilt-specific delays/wait/reposition). Shading by moving a vertical blind to a partial height remains a core CCA feature.
- Do not add other exclusions from CCA without an explicit user decision. Preserve the upstream cover-type and orientation handling as applicable.

## Debug and operational visibility (required)

Treat observability as a core feature, not a later polish task. Provide structured debug mode and clear logs; per-cover state/reason sensors or diagnostics; a detailed event timeline/history; pending timer and next-event visibility; evaluated condition snapshots; block/cancel/failure reasons; last command and observed result; and HA diagnostics export without credentials. Keep bounded history with a configurable retention policy. Make the UI answer: what is the desired target, what condition currently wins, what is blocking motion, what will happen next, and why did the last decision occur?
