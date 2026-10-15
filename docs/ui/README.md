# Latest UI design

## Approved redesign — 15 October 2026

The new design proposal is available as a [self-contained interactive HTML mockup](redesign-2026-10/CCA_zaluzie_redesign.html)
with a [complete design and acceptance criteria](redesign-2026-10/README.md).
Preview the [overview](redesign-2026-10/overview.png), [schedule](redesign-2026-10/schedule.png)
and [mobile layout](redesign-2026-10/mobile.png). The user approved this design for production implementation in 2026.12.0.
See [panel operation](../PANEL.md) for ordering, multi-selection and safe bulk editing.
The HTML remains a self-contained illustrative reference.

## Existing reference

The original visual reference is [CCA_zaluzie_UI.html](CCA_zaluzie_UI.html). Download the file and open it in a browser. It is a self-contained interactive prototype; its controls simulate behavior and do not connect to Home Assistant.

## Confirmed layout requirements

- Exactly one automation per cover and one independent row in the automation list.
- Keep the left automation list visible in both Overview and Configuration.
- Selecting a different cover changes the selected automation's context, including configuration.
- Use compact controls consistent with Entity Controller: time windows, switches, clickable section navigation, and grouped settings.
- Use clear Slovak labels such as â€śRuÄŤnĂ˝ reĹľimâ€ť, â€śVynĂştenĂ© ovlĂˇdanieâ€ť, â€śVetranieâ€ť and â€śZĂˇznamyâ€ť; avoid unexplained technical terms.
- Put short contextual help behind question-mark tooltips, available on hover and keyboard focus.
- Show the actions blocked by manual mode as individual checkboxes.
- Enable or disable dependent settings according to the feature switch and show their relationship clearly.
- Preserve draft values per cover when moving between configuration sections or changing the selected cover.
- Provide clear Save and Discard actions and a summary of the selected cover's draft configuration.
- Overview includes cover position, desired target/current reason, events and history, manual controls, automation state, and position reset.
- Position reset: full lowering, 60-second dwell at the lower end stop, then STOP. The prototype only simulates this sequence.
- No lamella/tilt controls; shading uses the vertical position of the whole cover.

## Agent use

Treat this file as a visual and interaction reference alongside [INTEGRATION_BRIEF.md](../INTEGRATION_BRIEF.md) and [CCA_REFERENCE.md](../CCA_REFERENCE.md). The prototype's example values, event records and simplified controls are illustrative. They do not supersede CCA's full applicable behavior or establish a complete production configuration schema. Preserve all required condition layers, priorities, diagnostics and state handling during implementation.

Snapshot saved to GitHub: 2026-10-11. Source: latest Library version 1, complete 141-line HTML file.
## Current overview in 2026.12.0

The production panel shows physical state, target, a conditional next action and
measured history. Simulation controls are in settings and its status is visible
in the overview. Prediction remains a read-only backend API, without an overview
section or automatic browser requests. See [panel operation](../PANEL.md).

The Add-cover link opens Home Assistant's native integration setup flow for `cca_zaluzie`.
