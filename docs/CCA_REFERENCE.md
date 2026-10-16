# CCA research notes — Cover Control Automation

## Source snapshot

- Upstream project: [hvorragend/ha-blueprints](https://github.com/hvorragend/ha-blueprints)
- Blueprint: [cover_control_automation.yaml](https://github.com/hvorragend/ha-blueprints/blob/main/blueprints/automation/cover_control_automation.yaml)
- Read on: 2026-10-11
- Upstream default-branch HEAD: `83e9925c3c0b1bbb96f6f55ef68c00e1c11870cf` (2026-10-04)
- Blueprint version in source: **2026.10.04**
- HA minimum declared by blueprint: **2025.4.0**
- CCA is a Home Assistant **automation blueprint**, not a custom integration. It creates one automation per cover and relies on user-created helpers.
- The notes below describe observed upstream behavior. They are a feature inventory/reference, not a promise that the new integration should copy every option.

## CCA concept and lifecycle

CCA computes a desired target for one cover from schedule, sun/weather, resident, window-contact, manual-override and force state. A trigger does not automatically mean a motor command: CCA evaluates constraints, derives/updates state, checks whether position and tilt already match within tolerance, optionally waits for a drive delay, checks pause/instance state again, then issues the movement and runs configured actions. Internal state is tracked separately from the physical cover state so paused/forced/overridden periods can be reconciled.

Every CCA automation requires:
1. a `cover` entity;
2. one dedicated `input_text` helper (254-character length in the documented quick start) to store JSON state;
3. optional sensors/helpers/entities for the enabled features.

A new integration should own persistent configuration and runtime state itself; requiring one manually created helper per blind would be a poor fit for the intended config-flow experience. CCA's architectural ceiling of one cover per automation and one manually provisioned helper per instance is not a product limit for this integration: support multiple covers/controllers under the integration, shared defaults with per-cover overrides, and HA-managed versioned storage. Retain useful behavioral limits (thresholds, early/late windows, waiting periods, retry bounds, tolerances, etc.) as configurable guardrails where they prevent unsafe or noisy operation; do not remove them merely because storage/UI differ.

## Cover model, positions, and tilt

### Supported cover types
- **Blind** (venetian): position plus optional tilt.
- **Shutter** (roller shutter): position.
- **Awning**: reversed position orientation.
- **Sunshade**: separate type-specific position semantics.

CCA's numeric values are not always intuitive: for blinds/shutters, open is commonly 100 and closed 0; awnings invert this (open 0, closed 100). The user's current hardware is ordinary vertical blinds/shutters that move up/down. The confirmed exclusions are venetian slat tilt / lamella-angle automation and, from 2026.12.6, tilted-window contact sensing and behavior. Preserve other CCA cover-type semantics, including orientation handling, as applicable. Use Home Assistant cover semantics consistently and expose calibrated position targets rather than assuming motor-native direction.

### Position handling
- Position source can be standard `current_position`, an alternate position attribute, or a custom sensor.
- Configurable open, close, ventilation, full-ventilation lockout, shading and alternate-shading positions.
- Position tolerance prevents needless repeat movement.
- Drive time is configurable for cases where the cover does not report useful position feedback.
- Values for distinct targets should not collide; validate sensible ordering/ranges for the selected cover type.
- Availability matters: CCA pauses decisions while the cover is unavailable because it cannot safely determine current position. Optional recovery catches up after availability returns.

### Explicitly excluded: lamella / tilt control
CCA supports tilt targets, up to four sun-elevation-based lamella positions, tilt tolerances, repositioning, wait modes, and ordered/combined position-plus-tilt commands. **None of that is available in CCA_zaluzie.** The only supported actuator axis is the cover's vertical open/close position. CCA sun shading still applies: it moves the whole blind to a configured partial height, with a distinct shading target and the same start/end conditions and lifecycle. The upstream tilt inputs remain in the source inventory below only to make the exclusion auditable.

## Schedule and ordinary morning/evening control

CCA has separate enable switches for morning opening and evening closing. Its time-control option defines **Early** and **Late** boundaries; Early is the earliest permitted move, Late is a guaranteed fallback move. Brightness and sun-elevation triggers typically act inside this window. If time control is disabled, all time boundaries and the Late safety-net behavior disappear; with no sensor trigger, enabling morning/evening alone does not provide a fixed schedule.

- Workday and non-workday opening and closing times are independently configured.
- A workday sensor for today can choose the relevant schedule; a second “tomorrow” sensor influences evening close planning.
- A calendar entity can provide open/close events matched by configured event titles.
- Opening can be triggered by brightness or sun elevation crossing thresholds, with optional stable-duration and hysteresis.
- Closing uses the corresponding dim/dark threshold and sun elevation logic.
- A setting controls AND/OR combination for brightness and sun-elevation logic.
- Optional “once per day” style behavior and other behavioral choices are under the selected feature options; inspect exact current input labels/defaults in the upstream YAML before implementing each.
- Resident mode constrains whether/when a schedule may open.

The key model for our timeline: retain both the planned earliest/latest window and the next actual decision/trigger, because “not yet”, “waiting for sensor”, and “guaranteed by latest time” are distinct states.

## Sun shading (partial close)

Shading is a separate state/lifecycle, not a synonym for evening close.

### Inputs and predicates
Triggers may use:
- solar azimuth start/end range;
- minimum/maximum sun elevation;
- brightness sensor with separate start/end thresholds and hysteresis;
- up to two temperature sensors and thresholds/hysteresis;
- weather forecast temperature and weather conditions;
- a custom condition sensor;
- independent temperature rules.

Start and end each have required AND conditions and optional OR conditions. This allows a user to require geometry plus one of several environmental checks, or build simpler combinations. A configurable shading position (and alternate position/entity trigger) selects the target. Venetian blinds can choose slat tilt by sun elevation.

### Two-phase behavior
1. **Pending:** a start/end trigger arms a wait and records a pending state.
2. **Re-check:** after waiting, all relevant conditions are evaluated again; move only if they still hold. Brightness start/end waits require the threshold state continuously for the configured duration; an interruption restarts that wait.
3. **Retry/end:** maximum start/end retry windows bound repeated attempts. Sun-position end may optionally end immediately when out of range.
4. **Movement:** the normal movement pipeline, tolerance, pause and actions apply.

Shading is time-window constrained unless configured otherwise. Pending must be visible in the UI as distinct from active shading; a timer or trace can be lost on restart/reload, so recovery and runtime state handling need explicit design.

## Ventilation and window contacts

- Full-open and tilted-window contacts may be configured independently.
- Full-open can drive to open or a dedicated full-ventilation position; tilted can drive to a partial-ventilation target.
- Open/tilted windows activate lockout protection so later close/shading behavior cannot trap an open window; tilted lockout has configurable policy.
- Contact-trigger delay and state delay debounce noisy contacts.
- Ventilation has additional conditions, separate start/end behavior and force entities.
- When ventilation is disabled, CCA ignores configured contacts throughout its logic (including scheduled close/shading/recovery), not merely the proactive ventilation movement.
- Force position outranks contact lockouts.

For our integration, show the ordinary open/closed contact and the reason for blocked movement. From 2026.12.6 the upstream tilted-window branches described above are excluded entirely. Ventilation targets remain distinct from contact state.

## Resident / sleep mode

An optional resident sensor represents awake/asleep or occupied/resting state. Depending on selected behavior, entering sleep can close immediately without waiting for schedule thresholds and keep the cover closed; waking can allow/open in the morning subject to schedule/light conditions. While the sleeping state is active, ordinary opening is prevented. It can also be used as a vacation switch, though a dedicated vacation concept may be clearer in our UI.

## Manual operation and overrides

CCA observes manual position/tilt changes and records a manual override. It can selectively block automatic opening, closing, ventilation and/or shading while the override is active.

Important distinctions:
- The override can be recorded without protecting the position from any later automatic action.
- If an allowed automatic action actually dispatches a movement, it can clear the override.
- A manual opening/closing inside its configured schedule window can be adopted as that day's scheduled event (state update only; it does not issue another movement).
- Reset can be time-based, after a duration, or when the cover reaches a configured position and dwells there.
- Reset may only clear the override, or optionally recompute/return to the current target.
- Overrides are separate from Force, which has higher priority.

The UI must distinguish user-requested manual position, detected manual override, override expiry/reset policy, and a blocked/allowed next automatic event. Do not infer manual intent from every position update: integration-originated commands and device feedback must be correlated to avoid false overrides.

## Force and pause

- Force entities can request immediate open, close, ventilation or shading.
- An active Force target is highest-priority desired target and overrides schedule, shading, ventilation, manual override and window lockout.
- Lower-priority target state continues to be tracked in the background; when Force clears, CCA can optionally recover to that state.
- Force Pause is a final movement inhibit. It suspends pending or newly planned movement without discarding desired target; it is rechecked before dispatch.
- Force states can be entities or input booleans depending on configuration.

For the new integration, use explicit priority arbitration and a reason field. Pause should not erase schedule/override/shading state. Provide a visible “resume/reconcile” policy after unpause.

## Conditions, actions, timing and recovery

- Global and per-event extra conditions can gate open, close, ventilation, shading start/tilt/end.
- Before/after actions can be configured for opening, closing, ventilation, shading start/end, manual change and override reset.
- A custom-action-only mode exists for integrations needing combined/nonstandard service calls; check the current actions documentation before mapping exact semantics.
- Optional fixed and random drive delays can stagger covers and reduce simultaneous motor starts.
- A drive-delay fix and instance-active guard address timer/restart edge cases.
- Optional outage/restart recovery can catch up missed events when an unavailable cover/sensor returns.
- Logging can target Home Assistant logbook and cover entity; trace count is configurable.
- A JSON status helper stores event/runtime state. Blueprint status uses compact keys; never reuse those internal keys as our public schema without a deliberate versioned model.

## Feature switches / input catalogue

Exact input IDs in the captured upstream source, grouped for research. The YAML is the authority for descriptions, selectors, defaults and conditional visibility.

- Base and modes: `blind`, `cover_status_helper`, `auto_options`, `time_control`, `brightness_sun_operator`, `individual_config`, `enable_recovery`, `instance_active`, `instance_active_value`.
- Cover mechanics: `position_source`, `custom_position_sensor`, `cover_type`, `open_position`, `close_position`, `ventilate_position`, `lockout_position`, `shading_position`, `shading_position_alt`, `shading_position_alt_entity`, `position_tolerance`, `drive_time`, `cover_tilt_wait_mode`, `cover_tilt_wait_timeout`, `tilt_delay`, `cover_tilt_config`, `cover_tilt_reposition_config`, `open_tilt_position`, `close_tilt_position`, `ventilate_tilt_position`, `tilt_position_tolerance`, `shading_tilt_position_0`, `shading_tilt_position_1`, `shading_tilt_elevation_1`, `shading_tilt_position_2`, `shading_tilt_elevation_2`, `shading_tilt_position_3`, `shading_tilt_elevation_3`.
- Time/calendar: `time_up_early`, `time_up_early_non_workday`, `time_up_late`, `time_up_late_non_workday`, `time_down_early`, `time_down_early_non_workday`, `time_down_late`, `time_down_late_non_workday`, `workday_sensor`, `workday_sensor_tomorrow`, `calendar_entity`, `calendar_open_title`, `calendar_close_title`.
- Open/close light/sun: `default_brightness_sensor`, `brightness_time_duration`, `brightness_up`, `brightness_down`, `brightness_hysteresis`, `default_sun_sensor`, `sun_time_duration`, `sun_elevation_mode`, `sun_elevation_up`, `sun_elevation_down`, `sun_elevation_up_sensor`, `sun_elevation_down_sensor`.
- Windows/ventilation: `contact_window_opened`, `contact_window_tilted`, `lockout_tilted_options`, `auto_ventilate_options`, `contact_delay_trigger`, `contact_delay_status`.
- Shading: `shading_conditions_start_and`, `shading_conditions_start_or`, `shading_conditions_end_and`, `shading_conditions_end_or`, `shading_custom_sensor`, `shading_azimuth_start`, `shading_azimuth_end`, `shading_elevation_min`, `shading_elevation_max`, `shading_brightness_sensor`, `shading_sun_brightness_start`, `shading_sun_brightness_end`, `shading_sun_brightness_hysteresis`, `shading_temperatur_sensor1`, `shading_min_temperatur1`, `shading_temperature_hysteresis1`, `shading_temperatur_sensor2`, `shading_min_temperatur2`, `shading_temperature_hysteresis2`, `shading_forecast_sensor`, `shading_forecast_type`, `shading_forecast_temp_sensor`, `shading_forecast_temp`, `shading_forecast_temp_hysteresis`, `shading_weather_conditions`, `shading_config`, `shading_independent_temp`, `shading_waitingtime_start`, `shading_start_max_duration`, `shading_waitingtime_end`, `shading_end_max_duration`, `shading_end_immediate_by_sun_position`.
- Presence/manual: `resident_sensor`, `resident_config`, `ignore_after_manual_config`, `manual_schedule_adoption`, `reset_override_config`, `auto_recover_after_manual_reset`, `reset_override_time`, `reset_override_timeout`, `reset_override_position`, `reset_override_position_dwell`.
- Guards, force, actions and diagnostics: `drive_delay_fix`, `drive_delay_random`, `auto_global_condition`, `auto_up_condition`, `auto_down_condition`, `auto_ventilate_condition`, `auto_ventilate_end_condition`, `auto_shading_start_condition`, `auto_shading_tilt_condition`, `auto_shading_end_condition`, `force_pause`, `auto_up_force`, `auto_down_force`, `auto_ventilate_force`, `auto_shading_start_force`, `auto_recover_after_force`, `auto_up_action_before`, `auto_up_action`, `auto_down_action_before`, `auto_down_action`, `auto_ventilate_action_before`, `auto_ventilate_action`, `auto_shading_start_action_before`, `auto_shading_start_action`, `auto_shading_end_action_before`, `auto_shading_end_action`, `auto_manual_action`, `auto_override_reset_action`, `check_config`, `check_config_debuglevel`, `enable_logbook`, `enable_logbook_cover`, `trace_count`.

## What to reuse and what not to cargo-cult

Reuse as **behavioral requirements**: target arbitration, pending/re-check timers, hysteresis/debounce, manual override semantics, window lockouts, pause/force priority, idempotent movement, movement sequencing, recoverability and transparent explanations.

Do not directly port the blueprint's implementation details as-is: per-cover helper requirement, automation trace as main diagnostic UI, compact JSON status keys, YAML selector organization, automation variables/branching patterns, or all 100+ inputs on one configuration form. The integration should offer progressive configuration and a clean per-cover model.

## Source and licensing caution

This repository currently documents observed behavior and design requirements; it does not contain copied upstream YAML or Python. The source blueprint describes itself as open-source and its embedded notice says attribution plus an upstream link are required for modifications. Before copying/adapting any source code, inspect the upstream repository's current license and confirm the permitted reuse and notice obligations. Link to upstream for concepts and maintain clear attribution.

## Capability mapping for CCA_zaluzie

| Upstream capability | Integration treatment |
|---|---|
| Morning/evening schedule, early/late windows, workday/non-workday | Preserve behavior; simplify setup with presets and an advanced section |
| Brightness/sun elevation triggers, stable duration, hysteresis, AND/OR | Preserve logic and expose only enabled sensor fields |
| Sun shading start/end, azimuth/elevation, brightness, temperatures, forecast/weather, custom conditions | Preserve all applicable CCA branches; shading moves the whole cover to partial height |
| Ventilation, open/tilted contacts, lockouts, debounce | Preserve ordinary open/closed contacts, ventilation, lockouts and debounce; exclude tilted-window contacts |
| Resident/sleep mode | Preserve |
| Manual override detection, blocking selections, adoption, timeout/reset/return | Preserve |
| Force open/close/ventilate/shading, force pause, background target tracking/recovery | Preserve priority semantics, document exact pause-versus-emergency policy |
| Before/after actions, custom actions, fixed/random delays, instance guards | Preserve where HA integration architecture permits; make action failures observable |
| Restart/outage recovery | Preserve as configurable policy and safely reconcile after restart |
| Logbook/automation traces and event diagnostics | Replace/add integration-native event history, decision timeline, structured debug logs and diagnostics; keep comparable detail |
| Position source, calibration, tolerances, unavailable handling | Preserve relevant vertical-position behavior |
| Cover type: awning/sunshade inverted position | Preserve CCA type semantics; user's current hardware is ordinary vertical blinds/shutters |
| Lamella tilt, up to four shading tilt bands, tilt wait/reposition | Explicitly excluded |

The aim is **behavioral parity with CCA except for lamella/tilt automation**, not a reduced “basic schedule” product. Keep the user-facing setup concise through progressive disclosure; retain advanced logic behind expandable settings. No feature should be quietly dropped: document anything that cannot map cleanly to HA as a decision or issue.

## Diagnostics and observability requirements

CCA's traces, status helper, event records and logbook support make its decisions inspectable. The integration should provide at least:
- a timeline of planned, pending, executed, cancelled, blocked and failed events;
- current computed mode/target, last evaluated conditions, winning priority and reasons lower-priority targets lost;
- sensor/contact values and threshold results used for each decision;
- configurable structured debug logging, clear warning/error logs, and HA diagnostics download with secrets excluded;
- per-cover last movement, last manual change/override, next schedule boundary, pending timer and availability;
- enough event history to inspect behavior over time, with bounded/retention-configurable storage;
- a direct path from a timeline event to related diagnostic detail, analogous to HA automation traces.

Unknown/unavailable inputs must be recorded as unknown and must not be silently treated as true/false in a way that causes movement.
