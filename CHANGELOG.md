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
