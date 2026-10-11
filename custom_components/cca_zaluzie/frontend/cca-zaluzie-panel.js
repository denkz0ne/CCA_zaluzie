/* Live HA panel: the controller API owns validation, persistence and motor execution. */
const esc = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const copy = (v) => structuredClone(v);
const optionNames = {
  blind: "Žalúzia",
  shutter: "Roleta",
  awning: "Markíza",
  sunshade: "Slnečná clona",
  current_position: "Štandardná poloha",
  position: "Atribút position",
  sensor: "Vlastný senzor",
  drive_time: "Čas jazdy motora",
  and: "Všetky (AND)",
  or: "Aspoň jedna (OR)",
  both: "Oba smery",
  rising_falling: "Otvorenie pri stúpaní, zatvorenie pri klesaní",
  azimuth: "Azimut slnka",
  elevation: "Výška slnka",
  brightness: "Jas",
  temperature1: "Teplota 1",
  temperature2: "Teplota 2",
  forecast: "Predpovedaná teplota",
  weather: "Počasie",
  custom: "Vlastná podmienka",
  daily: "Denná",
  hourly: "Hodinová",
  floor: "Zachovať vetraciu polohu",
  close_only: "Blokovať zatvorenie",
  all: "Blokovať všetky pohyby",
  none: "Bez blokácie",
  open: "Ranné otvorenie",
  close: "Večerné zatvorenie",
  ventilate: "Vetranie",
  shade_start: "Začiatok tienenia",
  shade_end: "Ukončenie tienenia",
};
const modes = {
  idle: "Čaká na podmienky",
  schedule: "Časový plán",
  shading: "Tienenie aktívne",
  ventilation: "Vetranie",
  window_lockout: "Otvorené okno",
  resident: "Režim obyvateľa",
  force_open: "Vynútené otvorenie",
  force_close: "Vynútené zatvorenie",
  force_shade: "Vynútené tienenie",
  force_ventilate: "Vynútené vetranie",
};
const inhibits = {
  manual: "Ručný režim",
  paused: "Pozastavené",
  disabled: "Vypnuté",
  unavailable: "Nedostupná",
  reset: "Reset polohy",
  contact_unknown: "Neznámy kontakt okna",
  resident_unknown: "Neznámy režim obyvateľa",
  condition: "Podmienka nepovoľuje pohyb",
  window_tilted: "Vyklopené okno blokuje pohyb",
  instance_disabled: "Automatizácia zablokovaná",
  manual_reset_hold: "Čaká na ďalšiu udalosť",
  startup_hold: "Po štarte čaká na ďalšiu udalosť",
  position_unknown: "Poloha nie je dostupná",
  movement_failed: "Pohyb sa nepotvrdil",
  schedule_window: "Čaká na časové okno",
  recovery_hold: "Po návrate čaká na ďalšiu udalosť",
  stop_hold: "Pohyb zastavený",
  wake_hold: "Čaká na ďalšie ranné podmienky",
  force_unknown: "Neznámy vstup vynúteného povelu",
  explicit_hold: "Pohyb zastavený",
  pending_confirmation: "Čaká na potvrdenie podmienok",
  unowned_target: "Cieľ nemá povolenú automatickú akciu",
  resident_open: "Režim obyvateľa blokuje otvorenie",
  contact_pending: "Čaká na potvrdenie kontaktu",
  behavior_guard: "Pohyb blokuje zvolená ochrana",
  once_per_day: "Denná akcia už bola vykonaná",
};
const eventNames = {
  decision: "Vyhodnotenie podmienok",
  command_requested: "Požadovaný pohyb",
  command_sent: "Povel odoslaný",
  command_completed: "Pohyb potvrdený",
  command_failed: "Pohyb zlyhal",
  command_interrupted: "Pohyb prerušený",
  command_stopped: "Pohyb zastavený",
  manual_requested: "Ručný povel",
  manual_detected: "Rozpoznaný ručný zásah",
  manual_reset: "Koniec ručného režimu",
  clear_override: "Ručný režim ukončený",
  reconcile: "Prepočítanie cieľa",
  reset_started: "Reset začal",
  reset_dwell: "Výdrž na doraze",
  reset_stopping: "Odosielanie STOP",
  reset_completed: "Reset dokončený",
  reset_failed: "Reset zlyhal",
  reset_cancelled: "Reset zrušený",
  reset_interrupted: "Reset prerušený reštartom",
  drive_pending: "Čaká pred pohybom",
  drive_cancelled: "Pohyb zrušený",
  action_failed: "Akcia zlyhala",
  custom_action_completed: "Vlastná akcia dokončená",
};
const clock = (ts) =>
  ts
    ? new Date(typeof ts === "number" ? ts * 1000 : ts).toLocaleTimeString(
        "sk-SK",
        { hour: "2-digit", minute: "2-digit" },
      )
    : "Pri zmene podmienok";
const styleURL = new URL("./panel.css", import.meta.url).href;
const extraCSS = `:host{display:block;min-height:100%;font:14px Roboto,'Segoe UI',Arial,sans-serif;color:var(--primary-text-color,#202a33);background:var(--primary-background-color,#f4f6f8);--surface:var(--card-background-color,#fff);--line:var(--divider-color,#e3e7eb);--muted:var(--secondary-text-color,#687681);--primary:var(--primary-color,#1677c8);--primary-soft:color-mix(in srgb,var(--primary) 12%,var(--surface))}button{font:inherit;border:1px solid var(--line);background:var(--surface);color:inherit;border-radius:8px;padding:8px 11px}button:disabled{opacity:.45;cursor:default}a{color:var(--primary)}.page-head a{margin-left:auto;text-decoration:none;padding:9px 12px;border:1px solid var(--line);border-radius:8px;background:var(--surface)}.cover-row{grid-template-columns:36px minmax(0,1fr)}.cover-sub{overflow-wrap:anywhere}.cover-name{display:block}.row-status{display:block;margin-top:6px;font-size:11px;color:#20845a}.panel{background:var(--surface)}.metrics{display:grid;grid-template-columns:1fr 1fr;gap:18px;padding:18px 20px}.metric-next{font-size:17px}.reason p{color:var(--muted)}.track-dot{position:absolute;top:4px;width:14px;height:14px;border:2px solid var(--surface);background:#237fba;border-radius:50%;padding:0;transform:translateX(-50%)}.track-dot.warn{background:#d18a1d}.track-dot.bad{background:#c64848}.track-dot.manual{background:#815bb0}.event-item{width:100%;text-align:left;border:0;border-bottom:1px solid var(--line);border-radius:0;grid-template-columns:54px minmax(0,1fr) auto}.event-item small{display:block;color:var(--muted);font-size:11px;margin-top:4px}.reset{margin:14px 20px;padding:13px;border:1px solid #f0d59f;border-radius:10px;background:#fff9eb;color:#77500d}.reset p{font-size:11px;line-height:1.5}.reset-clock{margin-left:auto;font-size:18px;font-variant-numeric:tabular-nums}.bottom-actions{padding:0 20px 18px;display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}.config-body h2{margin-bottom:16px}.field input,.field select{background:var(--surface);color:inherit;min-width:0}.choices{display:grid;grid-template-columns:1fr 1fr;gap:8px}.choice{display:flex;align-items:center;gap:9px;padding:10px;border:1px solid var(--line);border-radius:8px;font-size:12px;cursor:pointer}.choice input{width:15px;min-height:0;margin:0;accent-color:var(--primary)}.help span{left:0;transform:none}.form-footer{background:var(--surface)}.draft-state{margin-right:auto;font-size:11px;color:var(--muted)}.summary-row{display:flex;justify-content:space-between;gap:16px;border-bottom:1px solid var(--line);padding:11px 0;font-size:12px}.summary-row span{color:var(--muted);text-align:right;overflow-wrap:anywhere}.error{padding:12px 15px;margin-bottom:16px;border:1px solid #e6b0b0;border-radius:9px;background:#fff1f1;color:#9c3030;font-size:13px}.toast{pointer-events:none;opacity:1;max-width:calc(100vw - 30px)}.empty{padding:24px;color:var(--muted)}dialog{border:1px solid var(--line);border-radius:12px;background:var(--surface);color:inherit;max-width:680px;width:calc(100vw - 32px);padding:20px}dialog::backdrop{background:#0006}dialog pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;line-height:1.6;max-height:60vh;overflow:auto}.dialog-top{display:flex;align-items:center;justify-content:space-between}.condition-list{padding:0 20px 17px;font-size:12px;display:flex;gap:8px;flex-wrap:wrap}.condition-chip{padding:5px 8px;border-radius:6px;background:var(--primary-soft)}.advanced-note{padding:12px;border:1px solid var(--line);border-radius:9px;font-size:12px;line-height:1.6}.muted{color:var(--muted)}@media(max-width:700px){.metrics{gap:10px}.choices{grid-template-columns:1fr}.event-item{grid-template-columns:42px minmax(0,1fr)}.bottom-actions{justify-content:flex-start}.draft-state{flex-basis:100%}.page-head{gap:12px}.page-head a{margin-left:0}.config-body{padding:16px}.help span{max-width:210px}}`;

export class CCAZaluziePanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._controllers = new Map();
    this._drafts = new Map();
    this._baseline = new Map();
    this._dirty = new Set();
    this._selected = null;
    this._view = "overview";
    this._group = "cover";
    this._error = "";
    this._notice = "";
    this._busy = false;
    this._historyHours = 24;
    this.shadowRoot.addEventListener("click", (e) => this._click(e));
    this.shadowRoot.addEventListener("input", (e) => this._input(e));
    this.shadowRoot.addEventListener("change", (e) => this._input(e));
    this.shadowRoot.addEventListener("value-changed", (e) => this._input(e));
  }
  set hass(value) {
    this._hass = value;
    if (value && this.isConnected && this._connection !== value.connection)
      this._connect();
  }
  get hass() {
    return this._hass;
  }
  connectedCallback() {
    this._clock = setInterval(() => this._countdown(), 1000);
    if (this._hass) this._connect();
  }
  disconnectedCallback() {
    clearInterval(this._clock);
    if (this._unsubscribe) this._unsubscribe();
    this._unsubscribe = null;
    this._connection = null;
  }
  async _connect() {
    if (this._connecting) return;
    this._connecting = true;
    this._connection = this._hass.connection;
    try {
      const data = await this._hass.callWS({ type: "cca_zaluzie/list" });
      this._fields = data.fields;
      this._groups = data.groups;
      this._controllers.clear();
      for (const c of data.controllers) this._update(c);
      if (!this._controllers.has(this._selected))
        this._selected = data.controllers[0]?.entry_id;
      this._render();
      const unsub = await this._connection.subscribeMessage(
        (event) => {
          const p = event.event || event;
          if (p.controller) this._update(p.controller);
          else {
            this._controllers.delete(p.entry_id);
            if (this._selected === p.entry_id) {
              this._selected = this._controllers.keys().next().value;
              this._render();
              return;
            }
          }
          if (this._view === "settings") this._renderList();
          else this._render();
        },
        { type: "cca_zaluzie/subscribe" },
      );
      if (this.isConnected) this._unsubscribe = unsub;
      else unsub();
    } catch (e) {
      this._error = e.message || String(e);
      this._render();
    } finally {
      this._connecting = false;
    }
  }
  _update(c) {
    this._controllers.set(c.entry_id, c);
    this._offset = (c.server_time || Date.now() / 1000) - Date.now() / 1000;
    if (!this._dirty.has(c.entry_id)) {
      this._drafts.set(c.entry_id, copy(c.config));
      this._baseline.set(c.entry_id, copy(c.config));
    }
  }
  _renderList() {
    const list = this.shadowRoot.querySelector(".cover-list");
    if (list) list.innerHTML = this._list();
  }
  _list() {
    return [...this._controllers.values()]
      .map(
        (c) =>
          `<button class="cover-row ${c.entry_id === this._selected ? "selected" : ""}" data-cover="${esc(c.entry_id)}" aria-pressed="${c.entry_id === this._selected}"><span class="cover-icon">▥</span><span><strong class="cover-name">${esc(c.name)}</strong><small class="cover-sub">${esc(c.cover_entity)}</small><span class="row-status">● ${esc(!c.available ? "Nedostupná" : inhibits[c.decision.inhibit] || modes[c.decision.mode] || c.decision.mode)} ${c.position == null ? "" : `· ${esc(c.position)} %`}</span></span></button>`,
      )
      .join("");
  }
  _render() {
    const c = this._controllers.get(this._selected),
      body = c
        ? this._view === "settings"
          ? this._settings(c)
          : this._overview(c)
        : '<div class="panel empty">Pridaj prvú žalúziu cez nastavenia integrácie.</div>';
    this.shadowRoot.innerHTML = `<link rel="stylesheet" href="${styleURL}"><style>${extraCSS}</style><main class="main"><header class="page-head"><div><h1>Žalúzie</h1><p>Automatizácie a aktuálny priebeh jednotlivých žalúzií</p></div><a href="/config/integrations/dashboard?add=cca_zaluzie">＋ Pridať žalúziu</a></header>${this._error ? `<div class="error" role="alert">${esc(this._error)}</div>` : ""}<div class="tabs"><button class="tab ${this._view === "overview" ? "active" : ""}" data-view="overview">Prehľad</button><button class="tab ${this._view === "settings" ? "active" : ""}" data-view="settings">Konfigurácia</button></div><div class="overview"><aside class="panel automation-panel"><div class="panel-head"><h2>Automatizácie</h2><span class="count">${this._controllers.size} žalúzie</span></div><div class="cover-list">${this._list()}</div><div class="cover-footer">Samostatné ovládanie, stav a história každej žalúzie.</div></aside><section class="workspace-right">${body}</section></div></main>${this._notice ? `<div class="toast show" role="status">${esc(this._notice)}</div>` : ""}<dialog><div class="dialog-top"><h2>Detail udalosti</h2><button data-dialog-close aria-label="Zavrieť detail">✕</button></div><pre></pre></dialog>`;
    if (c && this._view === "settings") this._nativeSelectors();
    this._countdown();
  }
  _overview(c) {
    const d = c.decision,
      rt = c.runtime,
      r = rt.reset,
      resetting = r && ["closing", "dwell", "stopping"].includes(r.status),
      disabled = resetting || !c.available || this._busy ? "disabled" : "";
    const percent =
      c.position == null ? 0 : Math.max(0, Math.min(100, Number(c.position)));
    const resetNames = {
      closing: "Spúšťanie na doraz",
      dwell: "Výdrž na doraze · potom STOP",
      stopping: "Odosielanie STOP",
      failed: "Reset zlyhal",
      interrupted: "Reset bol prerušený",
      cancelled: "Reset bol zrušený",
      completed: "Reset bol dokončený",
    };
    const now = Date.now() / 1000 + (this._offset || 0),
      span = this._historyHours * 3600,
      start = now - span,
      history = c.events
        .filter((e) => Date.parse(e.at) / 1000 >= start)
        .slice(-150);
    const track = (name, filter) =>
      `<div class="timeline-row"><span class="track-name">${name}</span><div class="track">${history
        .filter(filter)
        .map(
          (e) =>
            `<button class="track-dot ${e.type.includes("failed") ? "bad" : e.type.includes("manual") ? "manual" : e.details?.inhibit ? "warn" : ""}" style="left:${Math.max(1, Math.min(99, (Date.parse(e.at) / 1000 - start) / (span / 100)))}%" data-event="${esc(e.id)}" title="${esc(eventNames[e.type] || e.type)} · ${clock(e.at)}" aria-label="${esc(eventNames[e.type] || e.type)} ${clock(e.at)}"></button>`,
        )
        .join("")}</div></div>`;
    return `<div class="panel detail"><div class="detail-top"><span class="big-cover">▥</span><div class="detail-title"><h2>${esc(c.name)}</h2><p>${esc(c.cover_entity)}</p></div><div class="detail-actions"><button data-action="open" ${disabled}><span aria-hidden="true">↑</span> Otvoriť</button><button data-action="close" ${disabled}><span aria-hidden="true">↓</span> Zatvoriť</button><button data-action="stop" ${!c.available ? "disabled" : ""}>■ Stop</button><button data-view="settings" aria-label="Nastavenia žalúzie">⚙</button></div></div><div class="status-strip"><span class="pill ${d.inhibit ? "amber" : "green"}">${esc(inhibits[d.inhibit] || modes[d.mode] || d.mode)}</span><span>Cieľ ${d.target == null ? "neurčený" : `${esc(d.target)} %`}</span>${d.pending ? `<span class="pill amber">${d.pending === "shade_start" ? "Čaká na potvrdenie tienenia" : "Čaká na koniec tienenia"}</span>` : ""}<button class="quiet-btn" data-action="${c.config.enabled ? "disable" : "enable"}" ${this._busy ? "disabled" : ""}>${c.config.enabled ? "Pozastaviť automatiku" : "Zapnúť automatiku"}</button></div><div class="metrics"><div><div class="metric-label">Aktuálna poloha</div><div class="metric-value">${c.position == null ? "Neznáma" : `${esc(c.position)} %`}</div><div class="position-meter"><span style="width:${percent}%"></span></div>${rt.estimated_position != null && c.position == null ? `<small class="muted">Odhad: ${esc(rt.estimated_position)} %</small>` : ""}</div><div><div class="metric-label">Najbližšia udalosť</div><div class="metric-value metric-next">${clock(d.next_at)}</div><small class="muted">${d.pending ? "Opätovné overenie podmienok" : "Časová hranica alebo zmena senzora"}</small></div></div><div class="reason"><strong>Prečo je žalúzia práve tu?</strong><p>${esc(d.reason)}${d.inhibit ? `<br>Pohyb blokuje: ${esc(inhibits[d.inhibit] || d.inhibit)}.` : ""}${rt.fault ? `<br>Chyba: ${esc(rt.fault)}` : ""}</p></div><div class="condition-list">${Object.entries(
      d.conditions || {},
    )
      .filter(([k]) => k.startsWith("shade.") && c.config.shading_enabled)
      .map(
        ([k, v]) =>
          `<span class="condition-chip">${esc(optionNames[k.split(".")[1]] || k)}: ${v === null ? "neznáme" : v === true ? "splnené" : v === false ? "nesplnené" : esc(v)}</span>`,
      )
      .join(
        "",
      )}</div><div class="section-head"><h3>Priebeh za posledných ${this._historyHours} hodín</h3><select aria-label="Obdobie histórie" data-history="true">${[6, 12, 24, 48].map((h) => `<option value="${h}" ${h === this._historyHours ? "selected" : ""}>${h} hodín</option>`).join("")}</select></div><div class="timeline"><div class="time-labels"><span>${clock(start)}</span><span>${clock(start + span / 4)}</span><span>${clock(start + span / 2)}</span><span>${clock(start + (span * 3) / 4)}</span><span>teraz</span></div>${track("Poloha", (e) => e.type.startsWith("command") || e.type.startsWith("reset"))}${track("Automatika", (e) => e.type === "decision" || e.type.startsWith("drive"))}${track("Blokácie", (e) => e.type.includes("manual") || Boolean(e.details?.inhibit))}</div><div class="section-head"><h3>Udalosti</h3><span class="sub">Podrobnosti po kliknutí</span></div><div class="event-list">${d.next_at ? `<div class="event-item"><span class="event-time">${clock(d.next_at)}</span><span>Naplánované vyhodnotenie<small>Pred pohybom sa znova overia podmienky.</small></span><span class="event-badge">plánované</span></div>` : ""}${
      [...c.events]
        .reverse()
        .slice(0, 50)
        .map(
          (e) =>
            `<button class="event-item" data-event="${esc(e.id)}"><span class="event-time">${clock(e.at)}</span><span>${esc(eventNames[e.type] || e.type)}<small>${esc(e.details?.reason || e.details?.error || modes[e.details?.mode] || "")}</small></span><span class="event-badge">${e.details?.target != null ? `${esc(e.details.target)} %` : ""}</span></button>`,
        )
        .join("") || '<p class="muted">Zatiaľ bez udalostí.</p>'
    }</div>${r ? `<div class="reset"><div class="reset-line"><span>${esc(resetNames[r.status] || r.status)}</span>${resetting ? `<span class="reset-clock" data-due="${Number(r.due) || 0}"></span>` : ""}</div><p>${esc(r.error || "Úplné spustenie, 60 sekúnd na doraze a následne STOP.")}</p>${resetting ? '<button class="quiet-btn" data-action="cancel_reset">Zrušiť reset</button>' : ""}</div>` : ""}<div class="bottom-actions">${c.config.shading_enabled ? `<button data-action="shade" ${disabled}>Tieniť</button>` : ""}${c.config.ventilation_enabled ? `<button data-action="ventilate" ${disabled}>Vetrať</button>` : ""}<button data-action="reset" ${disabled}>Reset polohy</button><button class="quiet-btn" data-action="clear_override" ${resetting ? "disabled" : ""}>Ukončiť ručný režim</button><button class="quiet-btn" data-action="reconcile" ${disabled}>Prepočítať cieľ</button></div></div>`;
  }
  _help(f) {
    return f.help
      ? `<button type="button" class="help" aria-label="Pomoc: ${esc(f.label)}" aria-describedby="help-${esc(f.key)}">?<span id="help-${esc(f.key)}" role="tooltip">${esc(f.help)}</span></button>`
      : "";
  }
  _field(f, cfg) {
    const value = cfg[f.key],
      disabled =
        this._busy ||
        f.key === "cover_entity" ||
        (f.depends && !cfg[f.depends]),
      id = `field-${f.key}`,
      common = `id="${id}" data-key="${esc(f.key)}" ${disabled ? "disabled" : ""}`;
    if (f.kind === "bool")
      return `<div class="field"><label class="switch-row" for="${id}"><span class="switch-copy"><strong>${esc(f.label)}</strong>${f.help ? `<small>${esc(f.help)}</small>` : ""}</span><input class="switch-input" role="switch" type="checkbox" ${common} ${value ? "checked" : ""}></label></div>`;
    if (f.kind === "multi")
      return `<div class="field full"><label>${esc(f.label)} ${this._help(f)}</label><div class="choices">${f.options.map((o) => `<label class="choice"><input type="checkbox" data-key="${esc(f.key)}" data-choice="${esc(o)}" ${value.includes(o) ? "checked" : ""} ${disabled ? "disabled" : ""}>${esc(optionNames[o] || o)}</label>`).join("")}</div></div>`;
    if (f.kind === "condition" || f.kind === "action")
      return customElements.get("ha-selector")
        ? `<div class="field full"><label>${esc(f.label)}</label><ha-selector data-native="${esc(f.key)}" data-key="${esc(f.key)}"></ha-selector></div>`
        : "";
    let control;
    if (f.kind === "select")
      control = `<select ${common}>${f.options.map((o) => `<option value="${esc(o)}" ${value === o ? "selected" : ""}>${esc(optionNames[o] || o)}</option>`).join("")}</select>`;
    else
      control = `<input type="${f.kind === "number" ? "number" : f.kind === "time" ? "time" : "text"}" ${common} value="${esc(value)}" ${f.kind === "number" ? `min="${f.minimum}" max="${f.maximum}" step="any"` : ""} ${f.kind === "entity" ? 'list="ha-entities" placeholder="Bez entity"' : ""}>`;
    return `<div class="field"><label for="${id}">${esc(f.label)} ${this._help(f)}</label><div class="input-with-unit">${control}${f.unit ? `<small>${esc(f.unit)}</small>` : ""}</div></div>`;
  }
  _settings(c) {
    const cfg = this._drafts.get(c.entry_id) || c.config,
      group = this._group,
      fields = Object.values(this._fields || {}).filter(
        (f) => f.group === group,
      );
    const summary =
      group === "summary"
        ? Object.entries(this._groups)
            .map(
              ([key, title]) =>
                `<h2>${esc(title)}</h2>${Object.values(this._fields)
                  .filter((f) => f.group === key)
                  .map(
                    (f) =>
                      `<div class="summary-row"><strong>${esc(f.label)}</strong><span>${esc(f.kind === "action" || f.kind === "condition" ? `${cfg[f.key].length} položiek` : f.kind === "bool" ? (cfg[f.key] ? "Zapnuté" : "Vypnuté") : Array.isArray(cfg[f.key]) ? cfg[f.key].map((x) => optionNames[x] || x).join(" · ") : optionNames[cfg[f.key]] || cfg[f.key] || "Bez nastavenia")}</span></div>`,
                  )
                  .join("")}`,
            )
            .join("")
        : "";
    return `<nav class="steps" aria-label="Sekcie konfigurácie">${Object.entries(
      { ...this._groups, summary: "Súhrn" },
    )
      .map(
        ([key, name]) =>
          `<button class="step ${group === key ? "active" : ""}" data-group="${esc(key)}">${esc(name)}</button>`,
      )
      .join(
        "",
      )}</nav><div class="panel form-card"><div class="config-heading"><span class="cover-icon">▥</span><div><strong>${esc(c.name)}</strong><small>${esc(c.cover_entity)} · nastavenia tejto žalúzie</small></div></div><div class="config-body"><h2>${esc(this._groups[group] || "Súhrn nastavení")}</h2>${group === "advanced" && !customElements.get("ha-selector") ? '<div class="advanced-note">Vlastné podmienky a akcie upravíš natívnym editorom Home Assistanta.<br><a href="/config/integrations/integration/cca_zaluzie">Otvoriť nastavenia integrácie →</a></div>' : ""}${summary || `<div class="form-grid">${fields.map((f) => this._field(f, cfg)).join("")}</div>`}<datalist id="ha-entities">${Object.entries(
      this._hass?.states || {},
    )
      .map(
        ([id, s]) =>
          `<option value="${esc(id)}">${esc(s.attributes?.friendly_name || id)}</option>`,
      )
      .join(
        "",
      )}</datalist></div><footer class="form-footer"><span class="draft-state">${this._dirty.has(c.entry_id) ? "Neuložené zmeny · iba táto žalúzia" : "Nastavenia uložené v Home Assistante"}</span><button class="quiet-btn" data-discard ${this._busy ? "disabled" : ""}>Zahodiť zmeny</button><button class="primary-btn" data-save ${this._busy ? "disabled" : ""}>Uložiť zmeny</button></footer></div>`;
  }
  _nativeSelectors() {
    for (const element of this.shadowRoot.querySelectorAll("[data-native]")) {
      const f = this._fields[element.dataset.native];
      element.hass = this._hass;
      element.selector = { [f.kind]: {} };
      element.value = copy(this._drafts.get(this._selected)[f.key]);
      element.disabled = this._busy;
    }
  }
  _input(event) {
    if (event.target.dataset?.history) {
      this._historyHours = Number(event.target.value);
      this._render();
      return;
    }
    if (this._busy) return;
    const input = event.target,
      key = input.dataset?.key;
    if (!key || !this._fields?.[key] || input.disabled) return;
    const cfg = this._drafts.get(this._selected),
      f = this._fields[key];
    if (input.dataset.choice) {
      const values = new Set(cfg[key]);
      if (input.checked) values.add(input.dataset.choice);
      else values.delete(input.dataset.choice);
      cfg[key] = [...values];
    } else
      cfg[key] =
        f.kind === "bool"
          ? input.checked
          : f.kind === "number"
            ? Number(input.value)
            : event.type === "value-changed"
              ? event.detail.value
              : input.value;
    this._dirty.add(this._selected);
    const state = this.shadowRoot.querySelector(".draft-state");
    if (state) state.textContent = "Neuložené zmeny · iba táto žalúzia";
    for (const dependent of Object.values(this._fields).filter(
      (f) => f.depends === key,
    ))
      for (const el of this.shadowRoot.querySelectorAll(
        `[data-key="${dependent.key}"]`,
      ))
        el.disabled = !cfg[key];
  }
  async _click(event) {
    const button = event.target.closest("button");
    if (!button || button.disabled) return;
    if (button.dataset.cover) {
      this._selected = button.dataset.cover;
      this._error = "";
      this._render();
      return;
    }
    if (button.dataset.view) {
      this._view = button.dataset.view;
      this._render();
      return;
    }
    if (button.dataset.group) {
      this._group = button.dataset.group;
      this._render();
      return;
    }
    if (button.hasAttribute("data-dialog-close")) {
      this.shadowRoot.querySelector("dialog").close();
      return;
    }
    if (button.dataset.event) {
      const e = this._controllers
        .get(this._selected)
        ?.events.find((e) => e.id === button.dataset.event);
      if (e) {
        const dialog = this.shadowRoot.querySelector("dialog");
        dialog.querySelector("pre").textContent = JSON.stringify(
          { udalosť: eventNames[e.type] || e.type, čas: e.at, ...e.details },
          null,
          2,
        );
        dialog.showModal();
      }
      return;
    }
    if (button.hasAttribute("data-discard")) {
      this._drafts.set(
        this._selected,
        copy(this._baseline.get(this._selected)),
      );
      this._dirty.delete(this._selected);
      this._error = "";
      this._render();
      return;
    }
    const selected = this._selected;
    if (button.hasAttribute("data-save")) {
      this._busy = true;
      this._error = "";
      this._notice = "";
      this._render();
      try {
        const config = copy(this._drafts.get(selected)),
          result = await this._hass.callWS({
            type: "cca_zaluzie/configure",
            entry_id: selected,
            config,
          });
        if (!result.saved) throw Error("Uloženie sa nepotvrdilo.");
        this._baseline.set(selected, copy(result.config || config));
        this._drafts.set(selected, copy(result.config || config));
        this._dirty.delete(selected);
        const c = this._controllers.get(selected);
        if (c) {
          c.config = copy(result.config || config);
          c.name = c.config.name;
        }
        this._notice = "Nastavenia uložené v Home Assistante.";
      } catch (e) {
        this._error = e.message || String(e);
      } finally {
        this._busy = false;
        this._render();
      }
      return;
    }
    if (button.dataset.action) {
      this._busy = true;
      this._error = "";
      this._notice = "";
      this._render();
      try {
        const c = await this._hass.callWS({
          type: "cca_zaluzie/control",
          entry_id: selected,
          action: button.dataset.action,
        });
        this._update(c);
      } catch (e) {
        this._error = e.message || String(e);
      } finally {
        this._busy = false;
        this._render();
      }
    }
  }
  _countdown() {
    for (const el of this.shadowRoot.querySelectorAll("[data-due]")) {
      const due = Number(el.dataset.due);
      if (!due) {
        el.textContent = "…";
        continue;
      }
      const left = Math.max(
        0,
        Math.ceil(due - Date.now() / 1000 - (this._offset || 0)),
      );
      el.textContent = `${Math.floor(left / 60)
        .toString()
        .padStart(2, "0")}:${(left % 60).toString().padStart(2, "0")}`;
    }
  }
}
if (!customElements.get("cca-zaluzie-panel"))
  customElements.define("cca-zaluzie-panel", CCAZaluziePanel);
