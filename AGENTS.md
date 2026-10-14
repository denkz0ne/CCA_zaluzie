# Instructions for coding agents

This repository is a new Home Assistant custom integration project. Model exactly one cover per automation/controller and one row per cover in the side panel. Provide a per-cover position-reset cycle: close fully, dwell at the lower end stop for 60 seconds, then stop; report progress and never mark success after an interrupted/failed cycle. The user's current hardware is ordinary vertical blinds/shutters. Preserve applicable CCA behavior; exclude only lamella/tilt control; preserve all other CCA behavior and cover-type semantics. Whole-blind partial-height sun shading remains supported. Strong state visibility, timelines, debug logs and diagnostics are requirements. Before implementation, read:
- [docs/INTEGRATION_BRIEF.md](docs/INTEGRATION_BRIEF.md)
- [docs/CCA_REFERENCE.md](docs/CCA_REFERENCE.md)

## Source-of-truth rules
- User-confirmed requirements are listed separately from proposals in the implementation brief.
- CCA feature notes are a snapshot of upstream `hvorragend/ha-blueprints` version 2026.10.04 at commit `83e9925c3c0b1bbb96f6f55ef68c00e1c11870cf`; verify upstream before implementing behavior because it changes.
- Entity Controller / “Svetlo v tme” is a UI and interaction reference. Do not copy its code or assume its internals without inspecting the relevant source.
- Treat material in the parent ChatGPT project's `sources/` directory as read-only reference. Never edit, move, rename or delete synced source files.
- Do not copy CCA source code into this repository until its current upstream license and attribution requirements have been checked.

## Engineering rules
- Keep the integration config-flow based; do not require YAML or manually created input_text state helpers for ordinary setup.
- Separate desired target, observed cover position, runtime mode, and reason for a decision.
- Make automation decisions idempotent, explainable and safe with unavailable/unknown states.
- Preserve configuration and entity identity across options updates and schema migrations.
- Keep this repository focused on the integration; record feature decisions and deferred work in docs/issues.
- Dry-run is per cover and defaults off. Every CCA motor service must pass through the motor gateway;
  simulated actions/scripts never execute and virtual progress must never be reported as hardware success.
- Prediction is a read-only scenario over copied runtime/input state. It must not call HA services,
  execute scripts/actions, or mutate a controller runtime, history, timer, or persisted storage.
- Label predictions as conditional/estimated when future inputs are unknown and never use a current
  sensor value as proof of a future value.
