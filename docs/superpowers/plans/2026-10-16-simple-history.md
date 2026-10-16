# Simple history implementation plan

**Goal:** Implement the user-approved filled day/night chart and useful event log exactly as the final preview.
**Spec:** User-approved CCA_historia_vypln.html (2026-10-16), followed by explicit implementation instruction.
**Architecture:** Keep all control and persistence behavior. Add read-only historical solar geometry to the existing history response. Render it with measured positions on one time axis. Filter only the overview presentation, preserving complete retained records.
**Tech stack:** Existing HA Python, Astral, native SVG/CSS/JS.

- [x] Add solar samples from HA location, using the same elevation convention as existing prediction, with horizon crossings.
- [x] Replace overview history with fixed 24h filled yellow/blue day/night and a plain measured-position line; retain unknown gaps and stable live updates.
- [x] Show last 20 meaningful physical events; move all retained events, technical evaluations and simulation into an accessible complete-record dialog with details.
- [x] Adapt existing UI regression expectations to approved removed controls; inspect actual rendered production panel.
- [x] Update documentation and release metadata; deliver through existing authorized PR/release workflow after CI.

No live HA writes or restarts. No new dependencies or motor/decision changes.

Final review found a pre-existing 50-event simulation truncation exposed by moving history into a dialog; removed the limit and corrected ordering so all retained records remain accessible. CI/release evidence follows in issue #23.
