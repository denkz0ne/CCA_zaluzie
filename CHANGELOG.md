# 2026.12.5

- Fix upgrade rendering: load the stylesheet with the panel module's release
  version, preventing old full-height drag rules from clipping cover cards.
- Add a visible one-shot mode section below the position slider, with paired
  start/end buttons, icons, current phase status and explanatory tooltips for
  shading and ventilation. Disabled features stay visible with a reason.
- Preserve attributes owned by native HA controls and the user's focused slider
  value during live updates; keep the insertion marker while dragging a card.
- Recalculate the next movement immediately after phase, mode or protection
  changes without running a two-day prediction for every measured position update.
- Clear active-motion presentation when device feedback becomes unavailable;
  keep measured position separate from the requested target.
- Reopen and correct the delivery gaps in issue #17; verify one-shot schedule
  adoption, early phase end, next-day behavior and new ventilation cycles.

# 2026.12.4

- Keep the side panel's DOM nodes stable during live updates so focused controls,
  selected covers, drafts and open dialogs survive state pushes.
- Show active opening or closing from the cover entity or current command, with
  the target separate from confirmed measured position. Simulation motion is
  marked explicitly; historical direction is no longer shown as current motion.
- Compact the automation list, remove the always-visible checkbox row and order
  arrows, retain the accessible drag grip and keyboard reorder, and add touch
  long-press multi-selection.
- Put shading and ventilation phase actions beside the main position controls;
  replace raw action keys with readable Slovak labels.
- Resolve issue #17 and document the current panel behavior.

# 2026.12.3

- Add a persisted 30-minute post-close safety lockout for enabled passage contacts.
- Limit open-contact confirmation to 2 seconds while retaining stable close confirmation.
- Rearm the lockout when the contact opens and leave lockout-off ventilation unchanged.
- Allow one explicit manual Close action to release the lockout only after current,
  stable contact closure; block slider and Force-driven descent during protection.
- Show remaining protection time and deferred close as the next planned action.
- Keep active shading when an ordinary contact opens without lockout; preserve serialized phases.
- Update issue #13 behavior, compatibility and current-version documentation.

# 2026.12.2

- Keep correction edits within ±20 percentage points of the original mode target
  and 120 seconds from the first accepted edit; later edits do not extend the window.
- Serialize active shading and ventilation phases, and merge a confirmed morning
  opening with shading when the movement is due within the internal 30-minute interval.
- Add one-shot start/end actions for shading and ventilation to the overview.
- Give an enabled open-contact lockout priority over Force-close, including when
  the contact state is unknown.
- Stabilize weather changes against each cover's selected weather states.
- Remove morning/evening lux and calendar decisions, migrate existing entries,
  and preserve the legacy lux sensor as an optional shading input.
- Preserve the Home Assistant 2026.9.0 minimum version.

# 2026.12.1

- Restore a live, read-only next-movement calculation in the cover overview.
- Show current sensor values beside the values and solar azimuth/elevation at the
  calculated movement time; display the active sun threshold and condition results.
- Start the scenario from the current time and retain manual protection and other
  live runtime constraints. Unknown future inputs are identified as assumptions.
- Keep measured position history alongside the calculated movement view.

# 2026.12.0

- Redesign the complete panel with Home Assistant controls, visible main switches,
  grouped schedules/settings, searchable entity pickers and contextual help.
- Add persistent cover ordering with a highlighted top grip, insertion marker,
  keyboard/touch alternatives and stable selection/drafts across reloads.
- Add Ctrl/Cmd or checkbox multi-selection and selective bulk edits with protected
  device-specific fields, validation of all candidates and stale-save detection.
- Show the last confirmed physical movement direction near the cover icon.
- Describe the next action, conditional timing and manual protection deferral;
  distinguish protection expiry from automatic return to the current target.
- Replace overview prediction with measured position history, optional Recorder
  reads and explicit gaps. Keep simulations separate and their controls in settings.
- Improve Slovak setting names/help, simplify the summary and dismiss success
  notifications automatically after four seconds.
- Preserve cover identities, existing settings, CCA mechanics, dry-run motor safety,
  the 60-second end-stop reset and Home Assistant 2026.9 minimum.

# 2026.11.1

- Automatically select reliable live cover position feedback and hide the
  source selector while detection succeeds.
- Show the source selector with a reason when feedback is missing or conflicting;
  block movement and reset until a usable source is available.
- Preserve explicit custom sensor and calibrated drive-time configurations.

# 2026.11.0

- Register the integration as a full Home Assistant service integration and repair the Add-cover flow.
- Add persistent per-cover dry-run with a guarded motor-service gateway, isolated virtual position,
  suppressed native actions, trace filters, and explicit simulated operation results.
- Add a read-only date-based prediction using the production decision engine, solar geometry,
  valid provider forecasts, and explicit conditional/estimated confidence.
- Preserve the Home Assistant 2026.9.0 minimum version.

# 2026.10.3

- Register CCA Žalúzie as a Home Assistant service integration instead of a helper.
- Fix the side-panel button so it opens the native CCA setup flow.

# 2026.10.2

- Lower the HACS minimum Home Assistant version to 2026.9.0.
- The previous 2026.10 floor reflected the development baseline; no required API excludes 2026.9.
- Verify the 2026.9 API baseline: Probatio, local brand images and frontend custom icons.
- Add Home Assistant 2026.9.4 to the GitHub test matrix.

# 2026.10.1

- Approved icon concept 02: balanced day/night sky above a blue roller shutter.
- Local integration branding: transparent 256/512 px PNG assets and editable SVG.
- Matching monochrome sidebar icon follows Home Assistant theme and selection color.
- Repository README and panel heading use the new identity.

# 2026.10.0

First installable release of CCA Žalúzie for Home Assistant 2026.10 or newer.

- Independent cover controllers with native setup/options flows and a Slovak sidebar panel.
- Early/Late morning/evening windows, workdays, calendar, brightness and sun-elevation gates.
- Vertical sun shading with separate start/end conditions, confirmation delays, hysteresis,
  temperatures, weather/forecast/custom inputs and alternate targets.
- Window contacts, ventilation, resident modes, manual overrides and last-activated Force arbitration.
- Explicit pause, recovery policies, native conditions and before/after actions.
- Full-close position reset with confirmed arrival, exactly 60 seconds dwell and STOP;
  failed/interrupted/cancelled operations never claim successful calibration.
- Versioned runtime persistence, bounded event history, trace details and diagnostics.
- HACS release archive, HA integration tests, browser tests, hassfest and HACS checks.

Lamella/tilt actuator control is intentionally excluded. Tilting a window remains
a supported contact state. Physical motors require installation-specific verification.
