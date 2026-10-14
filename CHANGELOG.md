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
