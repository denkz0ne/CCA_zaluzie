# Behavioral and visual references

CCA Žalúzie is an independently written Home Assistant custom integration.

- Cover Control Automation (CCA), by Carsten Volmer / hvorragend:
  https://github.com/hvorragend/ha-blueprints. Behavioral reference checked at
  `83e9925c3c0b1bbb96f6f55ef68c00e1c11870cf`, version 2026.10.04.
  Upstream's LICENSE is Creative Commons Attribution-NonCommercial 4.0 International:
  https://github.com/hvorragend/ha-blueprints/blob/main/LICENSE.
  This repository does not redistribute the upstream blueprint or port its source.
- Entity Controller / Svetlo v tme: UI interaction reference, inspected at
  https://github.com/denkz0ne/entity-controller/tree/v10-modernization.
  Its implementation is not copied into this integration.
- docs/ui/CCA_zaluzie_UI.html is the repository's approved visual prototype.
  The production stylesheet adapts that prototype and corrects spaced CSS units.

This implementation uses vertical cover targets and omits actuator lamella/tilt.
The behavior mapping and independent implementation choices are documented in
docs/FEATURE_MATRIX.md and the release design. External reference licensing
continues to apply to those external projects.
