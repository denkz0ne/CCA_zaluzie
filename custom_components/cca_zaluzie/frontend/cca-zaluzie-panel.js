// Production Home Assistant custom panel. Implementation follows browser contract tests.
class CCAZaluziePanel extends HTMLElement {
  constructor() { super(); this.attachShadow({mode: "open"}); }
}
customElements.define("cca-zaluzie-panel", CCAZaluziePanel);
