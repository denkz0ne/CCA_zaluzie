/* Live HA panel: the controller API owns validation, persistence and motor execution. */
import { iconPath } from "./icons.js";
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
  manual: "Ochrana manuálneho ovládania",
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
  schedule_window: "Čaká na čas otvorenia alebo zatvorenia",
  movement_merge: "Ranné otvorenie sa spojí s blízkym tienením",
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
  manual_requested: "Manuálny povel",
  manual_detected: "Rozpoznané manuálne ovládanie",
  manual_reset: "Koniec ochrany manuálneho ovládania",
  clear_override: "Ochrana manuálneho ovládania ukončená",
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
  would_dispatch: "Simulácia: motorový povel by sa odoslal",
  action_suppressed: "Simulácia: používateľská akcia zablokovaná",
  simulation_enabled: "Simulácia zapnutá",
  simulation_disabled: "Simulácia vypnutá",
  simulated_command_completed: "Simulovaný povel dokončený",
  simulated_reset_completed: "Simulovaný reset dokončený",
};
const clock = (ts) =>
  ts == null
    ? "Čaká na podmienky"
    : new Date(typeof ts === "number" ? ts * 1000 : ts).toLocaleTimeString(
        "sk-SK",
        { hour: "2-digit", minute: "2-digit" },
      );
const stamp = (ts) =>
  new Date(typeof ts === "number" ? ts * 1000 : ts).getTime();
const styleURL = new URL("./panel.css", import.meta.url).href;
const tip = (s) => `title="${esc(s)}"`;
const button = (text, attrs = "", help = text, cls = "btn flat") =>
  `<button class="${cls}" ${attrs} ${tip(help)}>${text}</button>`;
const native = (tag) => Boolean(customElements.get(tag));
const descriptions = {
  cover: "Identita, polohy a potvrdenie pohybu.",
  schedule: "Čas otvorenia a zatvorenia v pracovné a voľné dni.",
  light: "Jas, slnko a potvrdenie podmienok.",
  shading: "Výška celej žalúzie, slnečný rozsah a teploty.",
  windows: "Kontakty okien, bezpečnostné blokácie a vetranie.",
  manual: "Rozpoznanie a ochrana manuálneho ovládania.",
  resident: "Prítomnosť, obnova po výpadku a ochrana automatizácie.",
  advanced: "Vizuálne podmienky a akcie Home Assistanta.",
  records: "Udalosti, retencia a diagnostika.",
};
const sections = {
  cover: [
    ["Identita a typ", ["enabled", "name", "cover_entity", "cover_type"]],
    [
      "Cieľové polohy",
      [
        "open_position",
        "close_position",
        "shade_position",
        "vent_position",
        "lockout_position",
        "shade_alt_position",
      ],
    ],
    [
      "Spätná väzba a potvrdenie pohybu",
      [
        "position_source",
        "position_sensor",
        "position_tolerance",
        "drive_time",
        "movement_timeout",
      ],
    ],
    ["Večerné ochrany", ["prevent_higher_close", "prevent_lower_close_shaded"]],
  ],
  light: [
    [
      "Slnko",
      [
        "sun_enabled",
        "sun_sensor",
        "sun_threshold_mode",
        "sun_open",
        "sun_close",
        "sun_open_sensor",
        "sun_close_sensor",
        "sun_duration",
        "sun_direction",
      ],
    ],
  ],
  shading: [
    [
      "Tienenie a slnečný rozsah",
      [
        "shading_enabled",
        "shade_ignore_time",
        "shade_azimuth_start",
        "shade_azimuth_end",
        "shade_elevation_min",
        "shade_elevation_max",
        "shade_once",
      ],
    ],
    [
      "Podmienky začiatku a konca",
      [
        "shade_start_and",
        "shade_start_or",
        "shade_end_and",
        "shade_end_or",
        "shade_custom_sensor",
      ],
    ],
    [
      "Jas a stabilita",
      [
        "shade_lux_sensor",
        "shade_lux_start",
        "shade_lux_end",
        "shade_lux_hysteresis",
        "shade_start_delay",
        "shade_start_max",
        "shade_end_delay",
        "shade_end_max",
        "shade_end_immediate",
      ],
    ],
    [
      "Teplota 1",
      ["temperature_sensor1", "temperature1_min", "temperature1_hysteresis"],
    ],
    [
      "Teplota 2",
      [
        "temperature_sensor2",
        "temperature2_min",
        "temperature2_hysteresis",
        "shade_compare_sensor2",
      ],
    ],
    [
      "Predpoveď a počasie",
      [
        "forecast_entity",
        "forecast_type",
        "forecast_temp_sensor",
        "forecast_min",
        "forecast_hysteresis",
        "shade_weather",
      ],
    ],
    [
      "Alternatívne pravidlá a návrat",
      [
        "shade_independent",
        "shade_independent_temp",
        "shade_alt_entity",
        "shade_hold_hot",
        "prevent_shade_end_closed",
        "prevent_open_shade_end",
      ],
    ],
  ],
  windows: [
    [
      "Kontakty a potvrdenie",
      [
        "ventilation_enabled",
        "window_open",
        "window_tilted",
        "contact_delay",
        "contact_state_delay",
      ],
    ],
    [
      "Bezpečnostné blokácie",
      ["tilted_lockout", "tilted_blocks", "shading_over_ventilation"],
    ],
    [
      "Vetranie a návrat",
      [
        "vent_start_no_delay",
        "vent_return_delay",
        "vent_lower_from_above",
        "vent_after_shade",
        "vent_keep_full_tilt",
        "prevent_open_vent_end",
      ],
    ],
  ],
  manual: [
    [
      "Ochrana manuálneho ovládania",
      ["manual_enabled", "manual_timeout", "manual_blocks", "manual_return"],
    ],
    ["Denné ukončenie ochrany", ["manual_reset_daily", "manual_reset_time"]],
    [
      "Ukončenie potvrdenou polohou",
      [
        "manual_reset_position_enabled",
        "manual_reset_position",
        "manual_position_dwell",
      ],
    ],
    [
      "Prijatie manuálneho pohybu do plánu",
      ["manual_adopt_open", "manual_adopt_close"],
    ],
    [
      "Vynútené povely a pauza",
      [
        "force_open",
        "force_close",
        "force_ventilate",
        "force_shade",
        "force_pause",
        "force_recovery",
      ],
    ],
  ],
  resident: [
    [
      "Prítomnosť a povolenia",
      [
        "resident_sensor",
        "resident_close",
        "resident_open",
        "resident_allow_open",
        "resident_allow_shade",
        "resident_allow_vent",
      ],
    ],
    ["Obnova po výpadku a štarte", ["recovery_enabled", "startup_recovery"]],
    ["Ochrana automatizácie", ["instance_entity", "instance_value"]],
  ],
  records: [
    [
      "Denník udalostí",
      ["logbook", "logbook_cover", "retention_days", "history_limit"],
    ],
    ["Diagnostika", ["debug"]],
  ],
  advanced: [
    [
      "Spoločné pravidlá",
      [
        "custom_action_only",
        "drive_delay",
        "drive_random",
        "global_conditions",
      ],
    ],
    ...[
      "open",
      "close",
      "ventilate",
      "ventilate_end",
      "shade_start",
      "shade_end",
    ].map((k) => [
      {
        open: "Otvorenie",
        close: "Zatvorenie",
        ventilate: "Začiatok vetrania",
        ventilate_end: "Koniec vetrania",
        shade_start: "Začiatok tienenia",
        shade_end: "Koniec tienenia",
      }[k],
      [`${k}_conditions`, `${k}_before`, `${k}_after`],
    ]),
    ["Manuálne ovládanie", ["manual_after", "manual_reset_after"]],
  ],
};
export class CCAZaluziePanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._controllers = new Map();
    this._drafts = new Map();
    this._baseline = new Map();
    this._draftBases = new Map();
    this._draftRevisions = new Map();
    this._dirty = new Set();
    this._selected = null;
    this._selection = new Set();
    this._order = [];
    this._orderRevision = 0;
    this._bulkPatch = {};
    this._bulkRevisions = {};
    this._history = new Map();
    this._historyHours = 24;
    this._predictions = new Map();
    this._predictionKeys = new Map();
    this._predictionInFlight = new Map();
    this._view = "overview";
    this._group = "cover";
    this._error = "";
    this._notice = "";
    this._busy = false;
    for (const name of [
      "click",
      "input",
      "change",
      "value-changed",
      "keydown",
      "dragstart",
      "dragover",
      "dragleave",
      "drop",
      "dragend",
    ])
      this.shadowRoot.addEventListener(name, (e) => this._event(e));
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
    this._clock = setInterval(() => {
      this._countdown();
      this._loadPrediction();
    }, 1000);
    if (this.hass) this._connect();
  }
  disconnectedCallback() {
    clearInterval(this._clock);
    clearTimeout(this._toastTimer);
    this._unsubscribe?.();
    this._unsubscribe = null;
    this._connection = null;
  }
  async _connect() {
    if (this._connecting) return;
    this._connecting = true;
    const connection = this.hass.connection;
    this._connection = connection;
    this._unsubscribe?.();
    try {
      const data = await this.hass.callWS({ type: "cca_zaluzie/list" });
      if (this._connection !== connection) return;
      this._fields = data.fields;
      this._groups = data.groups;
      for (const c of data.controllers) this._update(c);
      this._applyOrder(
        data.order || data.controllers.map((c) => c.entry_id),
        data.order_revision,
      );
      if (!this._selected) {
        this._selected = this._order[0];
        if (this._selected) this._selection.add(this._selected);
      }
      this._render();
      const unsub = await connection.subscribeMessage(
        (event) => {
          const p = event.event || event;
          if (p.order) this._applyOrder(p.order, p.order_revision);
          if (p.controller) {
            this._update(p.controller);
            if (p.controller.entry_id === this._selected)
              this._loadPrediction();
          } else if (p.removed === true) this._remove(p.entry_id);
          if (this._view === "settings") this._renderList();
          else this._render();
        },
        { type: "cca_zaluzie/subscribe" },
      );
      if (this.isConnected && this._connection === connection)
        this._unsubscribe = unsub;
      else unsub();
      this._loadHistory();
      this._loadPrediction();
    } catch (e) {
      this._error = e.message || String(e);
      this._render();
    } finally {
      this._connecting = false;
      if (this._connection !== this.hass?.connection) this._connect();
    }
  }
  _applyOrder(order, revision) {
    if (revision != null && revision < this._orderRevision) return;
    this._order = [...new Set([...order, ...this._controllers.keys()])].filter(
      (id) => this._controllers.has(id),
    );
    this._orderRevision = revision ?? this._orderRevision;
  }
  _remove(id) {
    const index = this._order.indexOf(id);
    this._controllers.delete(id);
    this._order = this._order.filter((x) => x !== id);
    this._selection.delete(id);
    if (this._selected === id) {
      this._selected =
        this._order[Math.min(Math.max(index, 0), this._order.length - 1)];
      if (this._selected) this._selection.add(this._selected);
      this._notify("Automatizácia bola odstránená.");
    }
    this._render();
  }
  _update(c) {
    this._controllers.set(c.entry_id, c);
    if (!this._order.includes(c.entry_id)) this._order.push(c.entry_id);
    this._offset = (c.server_time || Date.now() / 1000) - Date.now() / 1000;
    this._baseline.set(c.entry_id, copy(c.config));
    if (!this._dirty.has(c.entry_id)) {
      this._drafts.set(c.entry_id, copy(c.config));
      this._draftBases.set(c.entry_id, copy(c.config));
      this._baseline.set(c.entry_id, copy(c.config));
      this._draftRevisions.set(c.entry_id, c.config_revision);
    }
  }
  _bulk() {
    return this._selection.size > 1;
  }
  _state(c) {
    return !c.available
      ? "Nedostupná"
      : inhibits[c.decision?.inhibit] ||
          modes[c.decision?.mode] ||
          "Čaká na podmienky";
  }
  _next(c) {
    const n = c.next_action;
    return n
      ? `${n.at ? clock(n.at) : n.earliest ? `Najskôr ${clock(n.earliest)}` : "Čaká na podmienky"} · ${n.label || "Ďalšia akcia"}`
      : "Čaká na podmienky";
  }
  _blind(c, large = false) {
    const pos =
      typeof c.position === "number"
        ? Math.min(100, Math.max(0, c.position))
        : null;
    const movement = c.last_movement;
    const dir = ["opening", "closing"].includes(movement?.direction)
      ? movement.direction
      : null;
    return `<span class="blind-wrap ${large ? "large" : ""}" role="img" aria-label="${pos == null ? "Neznáma poloha" : `Potvrdená poloha ${pos} %`}">${dir ? `<span class="movement ${dir}" data-direction="${dir}" ${tip(`Posledný pozorovaný pohyb: ${dir === "opening" ? "otváranie" : "zatváranie"} · ${clock(movement.at)}`)} aria-label="Posledný pozorovaný pohyb: ${dir === "opening" ? "otváranie" : "zatváranie"} · ${clock(movement.at)}">${dir === "opening" ? "▲" : "▼"}</span>` : ""}<svg viewBox="0 0 60 70" aria-hidden="true"><rect x="5" y="5" width="50" height="60" rx="2" fill="var(--primary-soft)" stroke="var(--secondary)" stroke-width="2"/><rect x="8" y="8" width="44" height="${pos == null ? 0 : (54 * (100 - pos)) / 100}" fill="var(--secondary)" opacity=".7"/><path d="M8 8h44 M8 15h44 M8 22h44 M8 29h44 M8 36h44 M8 43h44 M8 50h44 M8 57h44" stroke="var(--card)" stroke-width="1"/><path d="M3 4h54" stroke="var(--secondary)" stroke-width="4"/></svg></span>`;
  }
  _list() {
    return this._order
      .map((id, index) => {
        const c = this._controllers.get(id);
        return `<div class="automation ${this._selection.has(id) ? "multi-selected" : ""}" data-row="${esc(id)}"><div class="drag-strip"><button class="drag-grip" data-grip="${esc(id)}" draggable="true" aria-label="Presunúť automatizáciu ${esc(c.name)}" title="Presunúť automatizáciu · šípka hore/dole alebo potiahnuť"><span class="grip-dots" aria-hidden="true">⠿⠿⠿</span><span>Presunúť automatizáciu</span></button><div class="order-buttons">${button("↑", `data-order="${esc(id)}" data-delta="-1" ${index === 0 ? "disabled" : ""}`, "Presunúť vyššie", "order-button")}${button("↓", `data-order="${esc(id)}" data-delta="1" ${index === this._order.length - 1 ? "disabled" : ""}`, "Presunúť nižšie", "order-button")}</div></div><button class="cover-row ${id === this._selected ? "selected" : ""}" data-cover="${esc(id)}" aria-pressed="${id === this._selected}" ${tip("Zobraziť žalúziu. Ctrl/Cmd + kliknutie pridá do hromadného výberu bez zmeny zobrazenej žalúzie.")}><div class="cover-top">${this._blind(c)}<span class="cover-name">${esc(c.name)}</span><span class="cover-number">${c.position == null ? "?" : esc(c.position)}<small> %</small></span></div><span class="badge ${c.decision?.inhibit ? "amber" : ""}">${esc(this._state(c))}</span>${c.simulation?.enabled ? '<span class="badge amber">Simulácia</span>' : ""}<div class="cover-next">◷ <span>${esc(this._next(c))}</span></div></button><label class="select-cover" title="Vybrať na hromadnú úpravu"><input type="checkbox" data-multi="${esc(id)}" aria-label="Vybrať ${esc(c.name)} na hromadnú úpravu" ${this._selection.has(id) ? "checked" : ""}> Hromadný výber</label></div>`;
      })
      .join("");
  }
  _renderList() {
    const list = this.shadowRoot.querySelector(".cover-list");
    if (list) {
      const grip = this.shadowRoot.activeElement?.dataset?.grip;
      const scroll = list.scrollTop,
        x = list.scrollLeft;
      list.innerHTML = this._list();
      list.scrollTop = scroll;
      list.scrollLeft = x;
      if (grip)
        this.shadowRoot
          .querySelector(`[data-grip="${CSS.escape(grip)}"]`)
          ?.focus();
    }
  }
  _render() {
    const c = this._controllers.get(this._selected);
    const old = this.shadowRoot.querySelector(".cover-list");
    const scroll = old?.scrollTop || 0,
      x = old?.scrollLeft || 0;
    this.shadowRoot.innerHTML = `<link rel="stylesheet" href="${styleURL}"><header class="appbar"><div class="brand"><svg width="32" height="32" viewBox="0 0 256 256" aria-hidden="true"><path fill="currentColor" d="${iconPath}"/></svg><div><h1>Žalúzie</h1><small>Automatizácie a aktuálny priebeh</small></div></div><a class="btn" title="Pridať žalúziu cez nastavenia Home Assistanta" href="/config/integrations/dashboard/add?domain=cca_zaluzie">＋ Pridať žalúziu</a></header><main class="layout"><aside class="sidebar"><div class="sidebar-head"><h2>Automatizácie</h2><span>${this._controllers.size}</span></div><div class="cover-list">${this._list()}</div><small class="selection-hint">Ctrl/Cmd + kliknutie alebo zaškrtávacie políčko: hromadná úprava.</small></aside><section class="content"><nav class="tabs">${button("Prehľad", 'data-view="overview"', "Poloha, ovládanie a história", `tab ${this._view === "overview" ? "active" : ""}`)}${button("Konfigurácia", 'data-view="settings"', "Nastavenia vybraných žalúzií", `tab ${this._view === "settings" ? "active" : ""}`)}</nav>${this._error ? `<div class="error" role="alert">${esc(this._error)}</div>` : ""}${c ? `<div class="context"><div><div class="name">${esc(c.name)}</div><small>${esc(c.cover_entity)}</small></div><div class="head-switch"><div><strong>Automatické riadenie</strong><small>${c.config.enabled ? "Zapnuté · riadi podľa pravidiel" : "Vypnuté"}</small></div>${button(c.config.enabled ? "Zapnuté" : "Vypnuté", `data-action="${c.config.enabled ? "disable" : "enable"}" role="switch" aria-checked="${!!c.config.enabled}" ${this._busy ? "disabled" : ""}`, "Zmeniť automatické riadenie tejto žalúzie. Úprava je okamžitá.", "btn")}</div></div>${this._view === "settings" ? this._settings(c) : this._overview(c)}` : '<section class="card pad">Pridaj prvú žalúziu cez nastavenia integrácie.</section>'}</section></main>${this._notice ? `<div class="toast" role="status">${esc(this._notice)}${button("✕", 'data-dismiss aria-label="Zavrieť oznámenie"', "Zavrieť oznámenie")}</div>` : ""}<dialog><div class="dialog-header"><h3>Detail udalosti</h3>${button("✕", 'data-dialog-close aria-label="Zavrieť detail"', "Zavrieť detail")}</div><div class="dialog-body"></div></dialog>`;
    const list = this.shadowRoot.querySelector(".cover-list");
    if (list) {
      list.scrollTop = scroll;
      list.scrollLeft = x;
    }
    this._nativeSelectors();
    for (const el of this.shadowRoot.querySelectorAll(
      "ha-slider[data-position]",
    )) {
      el.value = Number(el.getAttribute("value"));
      el.min = 0;
      el.max = 100;
      el.step = 1;
      el.disabled = el.hasAttribute("disabled");
    }
    this._countdown();
  }
  _overview(c) {
    const d = c.decision || {},
      r = c.runtime?.reset,
      resetting = ["closing", "dwell", "stopping"].includes(r?.status),
      disabled = this._busy || resetting || !c.available;
    const ex = c.explanation;
    const shadingActive = Boolean(c.runtime?.shading);
    const ventilationActive = d.mode === "ventilation";
    const lockoutUntil = Number(c.runtime?.contact_lockout_until || 0);
    const serverNow = Number(c.server_time || Date.now() / 1000);
    const postCloseLockout = lockoutUntil > serverNow;
    const contactId = c.config.window_open;
    const contact = contactId && c.sensors?.[contactId];
    const verifiedClosedAt = Number(c.runtime?.contact_closed_verified_at || 0);
    const contactClosed = contact?.state === "off";
    const closeReleaseReady = Boolean(
      contactClosed &&
        verifiedClosedAt &&
        Number(contact.changed_at || 0) <= verifiedClosedAt,
    );
    const closeDisabled = disabled || (postCloseLockout && !closeReleaseReady);
    const positionDisabled = disabled || postCloseLockout;
    const lockoutNote = postCloseLockout
      ? `<div class="inline-note amber contact-lockout"><strong>Ochrana po zatvorení kontaktu</strong><span>Automatika počas ochrany nezatvorí žalúziu. Manuálne zatvorenie ju môže jednorazovo ukončiť, keď je kontakt potvrdene zatvorený. Zostáva <b class="reset-clock" data-due="${lockoutUntil}"></b>.</span></div>`
      : "";
    return `${c.simulation?.enabled ? '<div class="inline-note amber simulation-banner"><strong>SIMULÁCIA — motor je zablokovaný</strong><span>Simulované povely aj akcie sa iba zaznamenávajú.</span></div>' : ""}<div class="overview-grid"><section class="card pad"><div class="card-head"><h3>Poloha a ovládanie</h3><span class="badge">${esc(this._state(c))}</span></div><div class="position-layout">${this._blind(c, true)}<div><div class="position-number">${c.position == null ? "Neznáma" : `${esc(c.position)}<span> %</span>`}</div><p class="position-caption">${c.position == null ? "Zariadenie nepotvrdilo polohu" : "Potvrdená poloha zariadenia"}</p><p class="position-target">Aktuálny cieľ: <b>${d.target == null ? "Neurčený" : `${esc(d.target)} %`}</b></p>${c.runtime?.estimated_position != null && c.position == null ? `<small>Odhad: ${esc(c.runtime.estimated_position)} %</small>` : ""}${c.simulation?.shadow?.position != null ? `<small>Simulovaná poloha: ${esc(c.simulation.shadow.position)} %</small>` : ""}</div></div><div class="motor-controls">${button("↑ Otvoriť", `data-action="open" ${disabled ? "disabled" : ""}`, "Manuálne otvoriť cez bezpečnostné pravidlá.", "motor")}${button("■ Stop", `data-action="stop" ${!c.available ? "disabled" : ""}`, "Okamžite zastaviť pohyb.", "motor stop")}${button(postCloseLockout && closeReleaseReady ? "↓ Zatvoriť · jednorazovo" : "↓ Zatvoriť", `data-action="close" ${closeDisabled ? "disabled" : ""}`, postCloseLockout ? (closeReleaseReady ? "Vedome zatvoriť a jednorazovo ukončiť ochranu; kontakt je potvrdene zatvorený." : "Čaká sa na potvrdenie zatvoreného kontaktu.") : "Manuálne zatvoriť cez bezpečnostné pravidlá.", "motor")}</div>${lockoutNote}<div class="range-line"><label for="manual-position">Poloha</label>${this._positionControls(c, positionDisabled)}</div><div class="range-ends"><span>0 % · zatvorené</span><span>100 % · otvorené</span></div></section>${this._predictionBlock(c)}</div><section class="card reason-card"><div><h3>${esc(ex?.title || "Prečo je žalúzia v tejto polohe?")}</h3><p>${esc(ex?.summary || d.reason || "Zatiaľ bez vysvetlenia.")}</p>${button("Zobraziť podmienky a vstupy", "data-explanation", "Zobraziť skutočné vstupy posledného rozhodnutia.", "link")}</div></section>${this._historyBlock(c)}${r ? `<section class="card pad reset"><strong>${esc({ closing: "Spúšťanie na doraz", dwell: "Výdrž na doraze · potom STOP", stopping: "Odosielanie STOP", failed: "Reset zlyhal", interrupted: "Reset bol prerušený", cancelled: "Reset bol zrušený", completed: "Reset bol dokončený", simulated_completed: "Reset dokončený iba v simulácii" }[r.status] || r.status)}</strong>${resetting ? `<span class="reset-clock" data-due="${r.due || 0}"></span>${button("Zrušiť reset", 'data-action="cancel_reset"', "Prerušiť reset a zastaviť motor.")}` : ""}<p>${esc(r.error || "Úplné zatvorenie, 60 sekúnd na doraze a následne STOP.")}</p></section>` : ""}<div class="more-actions">${c.config.shading_enabled ? button(shadingActive ? "Ukončiť tienenie dnes" : "Začať tienenie teraz", `data-action="${shadingActive ? "phase_shade_end" : "phase_shade_start"}" ${disabled ? "disabled" : ""}`, shadingActive ? "Ukončiť aktuálne tienenie a zabrániť jeho opätovnému začatiu dnes." : "Začať tienenie hneď; platí do jeho bežného ukončenia alebo do konca dňa.") : ""}${c.config.ventilation_enabled ? button(ventilationActive ? "Ukončiť vetranie" : "Začať vetranie", `data-action="${ventilationActive ? "phase_vent_end" : "phase_vent_start"}" ${disabled ? "disabled" : ""}`, ventilationActive ? "Ukončiť aktuálne vetranie; ochrana kontaktu okna zostáva nadradená." : "Začať vetranie v nastavenej polohe; ochrana kontaktu okna zostáva nadradená.") : ""}${c.config.shading_enabled ? button("Poloha tienenia", `data-action="shade" ${disabled ? "disabled" : ""}`, "Jednorazovo presunúť žalúziu do nastavenej tieniacej polohy.") : ""}${c.config.ventilation_enabled ? button("Vetracia poloha", `data-action="ventilate" ${disabled ? "disabled" : ""}`, "Jednorazovo presunúť žalúziu do nastavenej vetracej polohy.") : ""}${button("Reset polohy", `data-reset ${disabled ? "disabled" : ""}`, "Zatvoriť, po potvrdení dorazu podržať 60 sekúnd a poslať STOP. Vyžaduje potvrdenie.")}${button("Ukončiť ochranu manuálneho ovládania", `data-action="clear_override" ${resetting ? "disabled" : ""}`, "Ukončiť ochranu; pohyb závisí od pravidiel.")}${button("Prepočítať cieľ", `data-action="reconcile" ${disabled ? "disabled" : ""}`, "Znova overiť pravidlá a aktuálny cieľ.")}</div>`;
  }
  async _loadPrediction() {
    const c = this._controllers.get(this._selected);
    if (!c || !this.hass || this._view !== "overview") return;
    const key = [
      Math.floor(Date.now() / 60000),
      c.config_revision || "",
      JSON.stringify(c.decision?.conditions?.inputs || {}),
      c.runtime?.manual_since || "",
      JSON.stringify(c.runtime?.hold_signature || null),
    ].join(":");
    if (this._predictionKeys.get(c.entry_id) === key) return;
    if (this._predictionInFlight.get(c.entry_id) === key) return;
    this._predictionKeys.set(c.entry_id, key);
    this._predictionInFlight.set(c.entry_id, key);
    try {
      const result = await this.hass.callWS({
        type: "cca_zaluzie/predict",
        entry_id: c.entry_id,
        days: 2,
        from_now: true,
      });
      if (this._predictionKeys.get(c.entry_id) === key)
        this._predictions.set(c.entry_id, result);
    } catch (error) {
      if (this._predictionKeys.get(c.entry_id) === key)
        this._predictions.set(c.entry_id, {
          error: error.message || String(error),
        });
    } finally {
      if (this._predictionInFlight.get(c.entry_id) === key)
        this._predictionInFlight.delete(c.entry_id);
      if (this._selected === c.entry_id && this._view === "overview")
        this._render();
    }
  }

  _predictionBlock(c) {
    const prediction = this._predictions.get(c.entry_id);
    const now = c.server_time || Date.now() / 1000;
    const event = prediction?.events?.find(
      (item) =>
        stamp(item.scenario_at) >= now * 1000 && item.status !== "blocked",
    );
    const config = c.config || {};
    const currentInputs =
      c.decision?.conditions?.inputs || prediction?.current?.inputs || {};
    const futureInputs = event?.conditions?.inputs || {};
    const fmt = (value) => {
      const number = Number(value);
      if (!Number.isFinite(number)) return "?";
      return new Intl.NumberFormat("sk-SK", { maximumFractionDigits: 1 })
        .format(number)
        .replace(/^-/, "−");
    };
    const solarEnabled = config.sun_enabled || config.shading_enabled;
    const sunNow = currentInputs[config.sun_sensor || "sun.sun"];
    const currentAzimuth = sunNow?.attributes?.azimuth;
    const currentElevation = sunNow?.attributes?.elevation;
    const projectedSolar = event?.solar;
    const thresholdKey =
      event?.type === "open"
        ? "sun_open"
        : event?.type === "close"
          ? "sun_close"
          : null;
    const solarThreshold = thresholdKey
      ? (event?.conditions?.thresholds?.[thresholdKey] ?? config[thresholdKey])
      : null;
    const solarRule = thresholdKey
      ? config.sun_threshold_mode === "fixed"
        ? `Hranica výšky slnka ${event.type === "open" ? "pre otvorenie" : "pre zatvorenie"}: ${event.type === "open" ? "≥" : "≤"} ${fmt(solarThreshold)}°`
        : `Hranicu výšky slnka určuje ${config[`sun_${event.type}_sensor`] || "nastavený senzor"}`
      : event?.type === "shade_start" && config.shading_enabled
        ? `Tienenie sa riadi azimutom ${fmt(config.shade_azimuth_start)}–${fmt(config.shade_azimuth_end)}°`
        : "";
    const solarRows = solarEnabled
      ? `<div class="prediction-condition"><strong>Slnko teraz</strong><span>Aktuálne: azimut ${currentAzimuth == null ? "?" : fmt(currentAzimuth)}° · výška ${currentElevation == null ? "?" : fmt(currentElevation)}°</span></div>${projectedSolar ? `<div class="prediction-condition"><strong>Slnko pri pohybe</strong><span>Pri pohybe: azimut ${fmt(projectedSolar.azimuth)}° · výška ${fmt(projectedSolar.elevation)}°</span></div>` : ""}${solarRule ? `<div class="prediction-condition"><strong>Podmienka slnka</strong><span>${esc(solarRule)}</span></div>` : ""}`
      : "";
    const inputEntities = [
      config.shading_enabled && config.shade_lux_sensor,
      config.shading_enabled && config.temperature_sensor1,
      config.shading_enabled && config.temperature_sensor2,
      config.ventilation_enabled && config.window_open,
      config.ventilation_enabled && config.window_tilted,
      config.resident_sensor,
      config.instance_entity,
      config.shade_custom_sensor,
      ...Object.keys(currentInputs).filter(
        (entity) => entity !== config.cover_entity && c.sensors?.[entity],
      ),
    ].filter((entity, index, all) => entity && all.indexOf(entity) === index);
    const readingText = (reading) => {
      if (!reading) return "Nedostupná";
      const parts = [
        reading.state && reading.state !== "unknown" ? reading.state : "",
      ];
      if (reading.value != null) parts.push(fmt(reading.value));
      for (const key of ["azimuth", "elevation", "temperature"]) {
        if (reading.attributes?.[key] != null)
          parts.push(
            `${key === "azimuth" ? "az." : key === "elevation" ? "výška" : "teplota"} ${fmt(reading.attributes[key])}${key === "temperature" ? " °C" : "°"}`,
          );
      }
      return parts.filter(Boolean).join(" · ") || "Bez hodnoty";
    };
    const sensorRows = inputEntities
      .map((entity) => {
        const actual = currentInputs[entity] || c.sensors?.[entity];
        const future = futureInputs[entity];
        const futureIsUnknown = Boolean(
          event?.assumptions?.includes(
            `Budúca hodnota ${entity} nie je známa.`,
          ),
        );
        const name = c.sensors?.[entity]?.attributes?.friendly_name || entity;
        const futureText = futureIsUnknown
          ? " · pri pohybe: neznáma hodnota"
          : future
            ? ` · pri pohybe: ${esc(readingText(future))}`
            : "";
        return `<div class="prediction-condition"><strong>${esc(name)}</strong><span>Teraz: ${esc(readingText(actual))}${futureText}</span></div>`;
      })
      .join("");
    const currentConditions = c.decision?.conditions || {};
    const projectedConditions = event?.conditions || {};
    const conditionKeys = new Set([
      ...Object.keys(currentConditions),
      ...Object.keys(projectedConditions),
    ]);
    const conditionLabel = (key) =>
      ({
        "light.open.sun": "Otvorenie · výška slnka",
        "light.close.sun": "Zatvorenie · výška slnka",
        "light.open.lux": "Otvorenie · jas",
        "light.close.lux": "Zatvorenie · jas",
        "condition.global": "Spoločné podmienky",
        "condition.open": "Podmienky otvorenia",
        "condition.close": "Podmienky zatvorenia",
        "schedule.open.day_known": "Ranný plán · pracovný deň",
        "schedule.close.day_known": "Večerný plán · pracovný deň",
      })[key] || key.replaceAll(".", " · ");
    const conditionState = (value) =>
      value === true ? "splnená" : value === false ? "nesplnená" : "neznáma";
    const conditionRows = [...conditionKeys]
      .filter(
        (key) =>
          (key.startsWith("condition.") ||
            key.startsWith("light.") ||
            key.startsWith("schedule.")) &&
          (typeof currentConditions[key] === "boolean" ||
            typeof projectedConditions[key] === "boolean"),
      )
      .map(
        (key) =>
          `<div class="prediction-condition"><strong>${esc(conditionLabel(key))}</strong><span>Teraz: ${conditionState(currentConditions[key])}${event ? ` · pri pohybe: ${conditionState(projectedConditions[key])}` : ""}</span></div>`,
      )
      .join("");
    const status = event
      ? {
          computed: "Vypočítané",
          estimated: "Odhad",
          conditional: "Podmienený scenár",
        }[event.status] || "Podmienený scenár"
      : prediction?.error
        ? "Výpočet nie je dostupný"
        : "Čas pohybu zatiaľ nemožno vypočítať";
    const detail = event
      ? `${esc(event.reason || "Pohyb podľa nastavených pravidiel.")} · cieľ ${esc(event.target)} %`
      : esc(
          c.decision?.inhibit
            ? inhibits[c.decision.inhibit] || c.decision.inhibit
            : "Nie je známy vykonateľný pohyb v nasledujúcich dvoch dňoch.",
        );
    const assumptions = event?.assumptions?.length
      ? `<p class="next-reason">Neznáme budúce vstupy: ${esc(event.assumptions.join(" "))}</p>`
      : "";
    const eventTime = event
      ? (() => {
          const value = new Date(event.scenario_at);
          const today = new Date(now * 1000);
          return value.toDateString() === today.toDateString()
            ? `Dnes · ${clock(event.scenario_at)}`
            : value.toLocaleString("sk-SK", {
                weekday: "short",
                day: "numeric",
                month: "short",
                hour: "2-digit",
                minute: "2-digit",
              });
        })()
      : "—";
    return `<section class="card pad"><div class="card-head"><h3>Vypočítaný ďalší pohyb</h3><span class="badge ${event?.status !== "computed" ? "amber" : ""}">${esc(status)}</span></div><div class="next-time">${esc(eventTime)}</div><div class="next-title">${esc(event?.type ? eventNames[event.type] || event.type : "Bez vypočítaného pohybu")}</div><p class="next-reason">${detail}</p>${solarRows || sensorRows || conditionRows ? `<div class="prediction-conditions">${solarRows}${sensorRows}${conditionRows}</div>` : ""}${assumptions}<p class="prediction-footnote">Čas vychádza z aktuálnych nastavení a výpočtu; pri neznámych budúcich vstupoch je podmienený.</p></section>`;
  }
  _positionControls(c, disabled) {
    const attrs = `data-position min="0" max="100" value="${c.position ?? 50}" ${disabled ? "disabled" : ""}`;
    return `${native("ha-slider") ? `<ha-slider id="manual-position" ${attrs} aria-label="Poloha – posuvník" title="Manuálne nastaviť polohu celej žalúzie"></ha-slider>` : `<input id="manual-position" type="range" ${attrs} aria-label="Poloha – posuvník" title="Manuálne nastaviť polohu celej žalúzie">`}<input type="number" ${attrs} aria-label="Presná manuálna poloha" title="Presne nastaviť polohu v percentách; potvrď Enterom alebo opustením poľa." class="position-exact"><span>%</span>`;
  }
  async _loadHistory() {
    const id = this._selected,
      hours = this._historyHours;
    if (!id) return;
    try {
      const data = await this.hass.callWS({
        type: "cca_zaluzie/history",
        entry_id: id,
        hours,
      });
      this._history.set(`${id}:${hours}`, data);
      if (
        this._selected === id &&
        this._view === "overview" &&
        this._historyHours === hours
      )
        this._render();
    } catch (e) {
      this._history.set(`${id}:${hours}`, { error: e.message || String(e) });
      if (this._selected === id && this._view === "overview") this._render();
    }
  }
  _historyBlock(c) {
    const h = this._history.get(`${c.entry_id}:${this._historyHours}`);
    const points = [
      ...new Map(
        [...(h?.points || []), ...(c.position_history || [])].map((p) => [
          p.at,
          p,
        ]),
      ).values(),
    ].sort((a, b) => stamp(a.at) - stamp(b.at));
    const start = stamp(
        h?.start || Date.now() / 1000 - this._historyHours * 3600,
      ),
      end = Math.max(stamp(h?.end || Date.now() / 1000), Date.now());
    let path = "",
      markers = "",
      last = null,
      hasGap = false;
    for (const p of points) {
      if (stamp(p.at) < start || stamp(p.at) > end) continue;
      if (p.position == null || !p.available) {
        last = null;
        hasGap = true;
        continue;
      }
      const x =
          50 +
          Math.max(0, Math.min(1, (stamp(p.at) - start) / (end - start))) * 900,
        y = 135 - p.position * 1.1;
      path += last ? ` H ${x} V ${y}` : ` M ${x} ${y}`;
      markers += `<circle data-measurement tabindex="0" role="button" cx="${x}" cy="${y}" r="4" fill="var(--primary)" aria-label="${new Date(p.at).toLocaleString("sk-SK")} · ${esc(p.position)} %" data-point-at="${esc(p.at)}" data-point-position="${esc(p.position)}"><title>${new Date(p.at).toLocaleString("sk-SK")} · ${esc(p.position)} %</title></circle>`;
      last = p;
    }
    const allEvents = [
      ...new Map(
        [...(h?.events || []), ...(c.events || [])].map((e) => [e.id, e]),
      ).values(),
    ]
      .filter((e) => stamp(e.at) >= start && stamp(e.at) <= end)
      .sort((a, b) => stamp(a.at) - stamp(b.at));
    const events = allEvents.filter((e) => !e.simulated),
      simulated = allEvents.filter((e) => e.simulated);
    return `<section class="card"><div class="history-head"><h3>História polohy a režimov</h3><select data-history aria-label="Obdobie histórie" title="Zobraziť skutočne nameranú históriu za zvolené obdobie">${[6, 24, 168].map((n) => `<option value="${n}" ${n === this._historyHours ? "selected" : ""}>${n === 168 ? "7 dní" : `${n} hodín`}</option>`).join("")}</select></div><div class="chart"><svg viewBox="0 0 1000 165" role="img" aria-label="Nameraná poloha od 0 do 100 percent; neznáme hodnoty prerušujú čiaru"><text x="2" y="28">100 %</text><text x="2" y="138">0 %</text><path d="M50 25H950 M50 80H950 M50 135H950" stroke="var(--line)" fill="none"/><path d="${path}" stroke="var(--primary)" stroke-width="3" fill="none"/>${markers}<text x="50" y="160">${new Date(start).toLocaleString("sk-SK", { day: "numeric", month: "numeric", hour: "2-digit", minute: "2-digit" })}</text><text x="830" y="160">${new Date(end).toLocaleString("sk-SK", { day: "numeric", month: "numeric", hour: "2-digit", minute: "2-digit" })}</text></svg>${h?.error ? `<p class="history-gap">História nie je dostupná: ${esc(h.error)}</p>` : !points.length ? '<p class="history-gap">Zatiaľ nie sú dostupné namerané údaje.</p>' : hasGap ? '<p class="history-gap">Medzera v meraní · neznáma alebo nedostupná poloha.</p>' : ""}</div><div class="legend"><span><i class="dot"></i>Nameraná poloha</span><span>Medzera = chýbajúce meranie</span></div>${this._recordedTracks(events, points, start, end)}<div class="history-events">${
      events
        .slice(-50)
        .reverse()
        .map(
          (e) =>
            `<button class="event-row" data-event="${esc(e.id)}" title="Zobraziť čas, typ a dôvod zaznamenanej udalosti"><small>${clock(e.at)}</small><span class="event-copy">${esc(eventNames[e.type] || e.type)}${e.simulated ? " · SIMULOVANÉ" : ""}<small>${esc(e.details?.reason || e.details?.error || "")}</small></span><b>${e.details?.target != null ? `${esc(e.details.target)} %` : ""}</b></button>`,
        )
        .join("") || '<p class="empty-state">Zatiaľ bez udalostí.</p>'
    }</div>${this._simulationTrace(simulated)}</section>`;
  }
  _recordedTracks(events, points, start, end) {
    const tracks = [
      ["modes", "Režimy", (e) => Boolean(e.details?.mode)],
      [
        "manual",
        "Manuálne ovládanie",
        (e) => e.type.includes("manual") || e.details?.inhibit === "manual",
      ],
      [
        "blocks",
        "Blokácie a pauza",
        (e) => Boolean(e.details?.inhibit) && e.details.inhibit !== "manual",
      ],
    ];
    return `<div class="recorded-tracks"><p class="field-hint">Zaznamenané udalosti · značky ukazujú potvrdené časy, bez odhadu trvania režimu.</p>${tracks
      .map(([id, label, filter]) => {
        const subset = events.filter(filter);
        return `<div class="recorded-track" data-track="${id}"><span>${label}</span><div class="mode-track">${subset.map((e) => `<button class="mode-dot" data-event="${esc(e.id)}" style="left:${Math.max(1, Math.min(99, ((stamp(e.at) - start) / (end - start)) * 100))}%" title="${clock(e.at)} · ${esc(eventNames[e.type] || e.type)} · ${esc(inhibits[e.details?.inhibit] || modes[e.details?.mode] || e.details?.reason || "")}" aria-label="${label} · ${clock(e.at)} · ${esc(inhibits[e.details?.inhibit] || modes[e.details?.mode] || eventNames[e.type] || e.type)}">●</button>`).join("") || "<small>Bez zaznamenanej udalosti</small>"}</div></div>`;
      })
      .join(
        "",
      )}<div class="recorded-track" data-track="availability"><span>Nedostupnosť</span><div class="mode-track">${
      points
        .filter(
          (p) => !p.available && stamp(p.at) >= start && stamp(p.at) <= end,
        )
        .map(
          (p) =>
            `<button class="mode-dot" data-measurement data-point-at="${esc(p.at)}" data-point-position="neznáma" style="left:${Math.max(1, Math.min(99, ((stamp(p.at) - start) / (end - start)) * 100))}%" title="${clock(p.at)} · Nedostupná poloha" aria-label="Nedostupná poloha · ${clock(p.at)}">×</button>`,
        )
        .join("") || "<small>Bez zaznamenanej nedostupnosti</small>"
    }</div></div></div>`;
  }
  _simulationTrace(events) {
    if (!events.length) return "";
    const filter = this._simulationFilter || "all";
    const visible = events.filter(
      (e) =>
        filter === "all" ||
        (filter === "errors" &&
          (/failed|interrupted/.test(e.type) || e.details?.error)) ||
        (filter === "blocked" &&
          (e.details?.inhibit || e.type === "action_suppressed")) ||
        (filter === "timers" && /timer|pending|dwell/.test(e.type)) ||
        e.type === filter,
    );
    return `<details class="simulation-trace"><summary title="Samostatné simulované udalosti, bez potvrdenia fyzického pohybu">Simulovaná história · ${events.length} udalostí · motor zablokovaný</summary><select data-simulation-filter aria-label="Filtrovať simuláciu" title="Zobraziť vybraný typ simulovaných udalostí">${[
      ["all", "Všetky"],
      ["decision", "Rozhodnutia"],
      ["timers", "Časovače"],
      ["would_dispatch", "Odoslalo by sa"],
      ["blocked", "Blokované"],
      ["errors", "Chyby"],
    ]
      .map(
        ([v, t]) =>
          `<option value="${v}" ${filter === v ? "selected" : ""}>${t}</option>`,
      )
      .join("")}</select>${
      visible
        .slice(-50)
        .reverse()
        .map(
          (e) =>
            `<button class="event-row" data-event="${esc(e.id)}" title="Detail simulovanej udalosti"><small>${clock(e.at)}</small><span>${esc(eventNames[e.type] || e.type)} · SIMULOVANÉ<small>${esc(e.details?.error || e.details?.reason || "")}</small></span><b>${e.details?.target != null ? `${esc(e.details.target)} %` : ""}</b></button>`,
        )
        .join("") || "<p>Bez simulovaných udalostí tohto typu.</p>"
    }</details>`;
  }
  _help(f) {
    return `<button type="button" class="help" data-help="${esc(f.key)}" aria-label="Pomoc: ${esc(f.label)}" title="${esc(f.help || `Nastaviť ${f.label.toLocaleLowerCase("sk")}${f.unit ? ` (${f.unit})` : ""}. Zmena sa použije po uložení.`)}">?</button>`;
  }
  _config() {
    if (!this._bulk()) return this._drafts.get(this._selected) || {};
    const ids = [...this._selection],
      base = copy(this._controllers.get(ids[0]).config);
    for (const key of Object.keys(base)) {
      if (
        ids.some(
          (id) =>
            JSON.stringify(this._controllers.get(id).config[key]) !==
            JSON.stringify(base[key]),
        )
      )
        base[key] = null;
    }
    return { ...base, ...this._bulkPatch };
  }
  _disabled(f, cfg) {
    return (
      this._busy ||
      f.key === "cover_entity" ||
      (this._bulk() && !f.bulk_editable) ||
      (f.depends && cfg[f.depends] === false)
    );
  }
  _field(f, cfg) {
    if (!f) return "";
    const v = cfg[f.key],
      mixed = this._bulk() && v == null,
      disabled = this._disabled(f, cfg);
    const common = `id="field-${f.key}" data-key="${esc(f.key)}" aria-label="${esc(f.label)}" ${tip(f.help || f.label)} ${disabled ? "disabled" : ""}`;
    let control = "";
    const nat = (tag) => `<${tag} data-native="${f.key}" ${common}></${tag}>`;
    if (f.kind === "bool")
      control = native("ha-switch")
        ? nat("ha-switch")
        : `<input type="checkbox" role="switch" ${common} ${v ? "checked" : ""} ${mixed ? "data-mixed" : ""}>`;
    else if (f.kind === "multi")
      control = `<div class="choices">${f.options.map((o) => `<label class="chip"><input type="checkbox" data-choice="${esc(o)}" data-key="${f.key}" ${Array.isArray(v) && v.includes(o) ? "checked" : ""} ${disabled ? "disabled" : ""} ${tip(f.help || f.label)}> ${esc(optionNames[o] || o)}</label>`).join("")}</div>`;
    else if (f.kind === "entity")
      control = native("ha-entity-picker")
        ? nat("ha-entity-picker")
        : `<div class="entity-fallback"><input ${common} value="${esc(v)}" placeholder="Hľadať názov alebo ID entity" autocomplete="off" data-entity-search><div class="entity-results" data-results="${f.key}" hidden></div></div>`;
    else if (f.kind === "condition" || f.kind === "action")
      control = native("ha-selector")
        ? nat("ha-selector")
        : `<div class="builder" data-key="${f.key}" aria-disabled="${disabled}"><p>${Array.isArray(v) && v.length ? `${v.length} uložených položiek` : "Bez doplnkových položiek."}</p><small>Vizuálny editor je dostupný v Home Assistante.</small>${disabled ? "" : '<a href="/config/integrations/integration/cca_zaluzie" title="Otvoriť natívny konfiguračný editor">Otvoriť nastavenia integrácie →</a>'}</div>`;
    else if (f.kind === "select")
      control = `<select ${common}>${mixed ? '<option value="">Rôzne hodnoty</option>' : ""}${f.options.map((o) => `<option value="${esc(o)}" ${o === v ? "selected" : ""}>${esc(optionNames[o] || o)}</option>`).join("")}</select>`;
    else if (f.kind === "time")
      control = native("ha-time-input")
        ? nat("ha-time-input")
        : `<input type="time" ${common} value="${esc(v)}">`;
    else if (f.kind === "number" && f.unit === "s") {
      if (native("ha-duration-input")) control = nat("ha-duration-input");
      else {
        const unit =
          this._durationUnits?.[f.key] ||
          ((v || 0) >= 3600 && (v || 0) % 3600 === 0
            ? 3600
            : (v || 0) >= 60 && (v || 0) % 60 === 0
              ? 60
              : 1);
        control = `<div class="input-frame"><input type="number" ${common} data-duration="${unit}" min="${f.minimum / unit}" max="${f.maximum / unit}" step="any" value="${mixed ? "" : Number(v) / unit}" placeholder="${mixed ? "Rôzne hodnoty" : ""}"><select data-duration-unit="${f.key}" aria-label="Jednotka: ${esc(f.label)}" ${tip("Zmeniť zobrazenie trvania bez zmeny uloženého času.")} ${disabled ? "disabled" : ""}>${[
          [1, "sekundy"],
          [60, "minúty"],
          [3600, "hodiny"],
        ]
          .map(
            ([n, t]) =>
              `<option value="${n}" ${n === unit ? "selected" : ""}>${t}</option>`,
          )
          .join("")}</select></div>`;
      }
    } else
      control = `<div class="input-frame">${f.kind === "number" && f.unit === "%" ? `<input type="range" ${common.replace(`id="field-${f.key}"`, "").replace(`aria-label="${esc(f.label)}"`, `aria-label="${esc(f.label)} – posuvník"`)} min="${f.minimum}" max="${f.maximum}" value="${v ?? 50}">` : ""}<input type="${f.kind === "number" ? "number" : "text"}" ${common} value="${esc(v)}" placeholder="${mixed ? "Rôzne hodnoty" : ""}" ${f.kind === "number" ? `min="${f.minimum}" max="${f.maximum}" step="any"` : ""}>${f.unit ? `<span class="unit">${esc(f.unit)}</span>` : ""}</div>`;
    return `<div class="field ${["action", "condition", "multi"].includes(f.kind) ? "full" : ""} ${disabled ? "field-disabled" : ""}"><div class="field-title"><label for="field-${f.key}">${esc(f.label)}</label> ${this._help(f)}</div>${control}${mixed ? '<small class="mixed">Rôzne hodnoty · zmení sa iba po výslovnej úprave</small>' : ""}${f.help ? `<p class="field-hint">${esc(f.help)}</p>` : ""}${this._bulk() && !f.bulk_editable ? "<small>Chránené pri hromadnej úprave</small>" : ""}</div>`;
  }
  _block(title, keys, cfg) {
    keys = keys.filter((k) => this._fields[k]);
    const first = this._fields[keys[0]],
      main = first?.kind === "bool" ? first : null;
    return `<section class="card settings-card"><div class="feature-header"><div class="feature-title"><h3>${esc(title)}</h3>${main ? this._help(main) : ""}</div>${main ? this._field(main, cfg) : ""}</div><div class="field-grid">${keys
      .filter((k) => k !== main?.key)
      .map((k) => this._field(this._fields[k], cfg))
      .join("")}</div></section>`;
  }
  _settings(c) {
    const cfg = this._config(),
      g = this._group;
    let body = "";
    if (g === "summary") {
      body = Object.entries(this._groups)
        .map(([id, title]) => {
          const fields = Object.values(this._fields).filter(
            (f) =>
              f.group === id &&
              ((["time", "entity"].includes(f.kind) && c.config[f.key]) ||
                (f.kind === "number" && ["%", "s"].includes(f.unit)) ||
                (f.kind === "bool" && c.config[f.key]) ||
                (["condition", "action"].includes(f.kind) &&
                  c.config[f.key]?.length)),
          );
          return `<section class="card summary-card"><h3>${esc(title)}</h3>${fields
            .slice(0, 12)
            .map(
              (f) =>
                `<div class="summary-row"><span>${esc(f.label)}</span><b>${esc(this._format(f, c.config[f.key]))}</b></div>`,
            )
            .join(
              "",
            )}${button("Upraviť", `data-group="${id}"`, "Upraviť túto kategóriu")}</section>`;
        })
        .join("");
      body = `<div class="summary-grid">${body}</div>`;
    } else {
      let blocks = sections[g] || [];
      if (g === "schedule")
        blocks = [
          ["Riadenie podľa času", ["time_enabled"]],
          [
            "Ranné otvorenie",
            [
              "morning_enabled",
              "morning_early",
              "morning_late",
              "morning_early_free",
              "morning_late_free",
              "open_once",
            ],
          ],
          [
            "Večerné zatvorenie",
            [
              "evening_enabled",
              "evening_early",
              "evening_late",
              "evening_early_free",
              "evening_late_free",
              "close_once",
            ],
          ],
          ["Pracovné dni", ["workday_sensor", "workday_tomorrow"]],
        ];
      const used = new Set(blocks.flatMap((b) => b[1]));
      const remaining = Object.values(this._fields)
        .filter((f) => f.group === g && !used.has(f.key))
        .map((f) => f.key);
      if (remaining.length)
        blocks = [...blocks, ["Ďalšie nastavenia", remaining]];
      body = blocks
        .map(([title, keys]) =>
          this._block(
            title,
            keys.filter(
              (k) =>
                !(
                  k === "position_source" &&
                  c.position_source?.automatic &&
                  c.position_source.selected
                ),
            ),
            cfg,
          ),
        )
        .join("");
      if (g === "schedule") {
        const cards = blocks.map(([title, keys]) =>
          this._block(title, keys, cfg),
        );
        body =
          cards[0] +
          `<div class="schedule-pair">${cards[1]}${cards[2]}</div>` +
          cards.slice(3).join("");
      }
      if (g === "cover")
        body += `<section class="card settings-card"><div class="feature-header"><h3>Simulácia bez pohybu motora</h3></div><p>Živé vstupy, motorové povely aj vlastné akcie sa iba zaznamenávajú.</p>${button(c.simulation?.enabled ? "Vypnúť simuláciu" : "Zapnúť simuláciu", `data-action="${c.simulation?.enabled ? "simulation_off" : "simulation_on"}" ${this._bulk() || this._busy ? "disabled" : ""}`, "Zmeniť simuláciu iba pre zobrazenú žalúziu. Zmena je okamžitá.")}<small>${c.simulation?.enabled ? "Zapnutá · motor zablokovaný" : "Vypnutá"}</small></section>`;
    }
    return `${this._bulk() ? `<div class="inline-note amber bulk-banner"><strong>Hromadná úprava · ${this._selection.size} automatizácie</strong><span>Uložia sa iba výslovne upravené povolené polia. Chránené polia sa nemenia.</span>${button("Zrušiť hromadný výber", "data-clear-selection", "Zobraziť návrh jednej žalúzie.")}</div>` : ""}<nav class="section-nav" aria-label="Sekcie konfigurácie">${Object.entries(
      { ...this._groups, summary: "Súhrn" },
    )
      .map(([id, name]) =>
        button(
          esc(name),
          `data-group="${id}" aria-pressed="${g === id}"`,
          descriptions[id] || "Rozhodujúce uložené nastavenia",
          `section-tab ${g === id ? "active" : ""}`,
        ),
      )
      .join(
        "",
      )}</nav><div class="section-intro"><h2>${esc(this._groups[g] || "Súhrn nastavení")}</h2><p>${esc(descriptions[g] || "Uložené hodnoty vybranej žalúzie.")}</p></div>${g === "cover" && c.position_source?.automatic && !c.position_source.selected ? '<div class="inline-note amber">Home Assistant hlási dve rozdielne polohy alebo chýbajúcu polohu. Vyber zdroj spätnej väzby ručne.</div>' : ""}<div class="settings-stack">${body}</div><footer class="savebar"><p class="draft-state">${this._bulk() ? `${Object.keys(this._bulkPatch).length} výslovne upravených polí` : this._dirty.has(c.entry_id) ? "Neuložené zmeny · iba táto žalúzia" : "Nastavenia sú uložené"}</p><div class="actions">${button("Zahodiť zmeny", `data-discard ${this._busy ? "disabled" : ""}`, "Obnoviť posledné uložené hodnoty.")}${button(this._bulk() ? `Uložiť zmeny (${this._selection.size})` : "Uložiť zmeny", `data-save ${this._busy ? "disabled" : ""}`, "Uložiť upravené nastavenia.", "btn primary")}</div></footer>`;
  }
  _format(f, v) {
    return f.kind === "bool"
      ? v
        ? "Zapnuté"
        : "Vypnuté"
      : Array.isArray(v)
        ? `${v.length} položiek`
        : f.kind === "select"
          ? optionNames[v] || v
          : `${v ?? "—"}${f.unit ? " " + f.unit : ""}`;
  }
  _nativeSelectors() {
    const cfg = this._config();
    for (const el of this.shadowRoot.querySelectorAll("[data-native]")) {
      const f = this._fields[el.dataset.native];
      el.hass = this.hass;
      el.disabled = Boolean(this._disabled(f, cfg));
      el.label = f.label;
      el.value = copy(cfg[f.key]);
      if (f.kind === "bool") {
        el.checked = Boolean(cfg[f.key]);
        el.indeterminate = this._bulk() && cfg[f.key] == null;
      }
      if (f.kind === "entity") {
        el.includeDomains =
          f.key === "cover_entity"
            ? ["cover"]
            : f.key.includes("calendar")
              ? ["calendar"]
              : f.key === "forecast_entity"
                ? ["weather"]
                : f.key === "sun_sensor"
                  ? ["sun"]
                  : undefined;
        el.allowCustomEntity = false;
      }
      if (f.kind === "condition" || f.kind === "action")
        el.selector = { [f.kind]: {} };
      if (f.kind === "time") {
        el.value = cfg[f.key] || "";
        el.locale = this.hass.locale || { language: "sk", time_format: "24" };
      }
      if (f.kind === "number" && f.unit === "s") {
        const seconds = Number(cfg[f.key]) || 0;
        el.data = {
          hours: Math.floor(seconds / 3600),
          minutes: Math.floor((seconds % 3600) / 60),
          seconds: seconds % 60,
        };
        el.enableDay = false;
        el.enableSecond = true;
        el.enableMillisecond = false;
        el.min = f.minimum;
        el.max = f.maximum;
      }
    }
    for (const el of this.shadowRoot.querySelectorAll("[data-mixed]"))
      el.indeterminate = true;
  }
  _notify(message) {
    clearTimeout(this._toastTimer);
    this._notice = message;
    this._toastTimer = setTimeout(() => {
      this._notice = "";
      this.shadowRoot.querySelector(".toast")?.remove();
    }, 4000);
  }
  _dialog(title, html) {
    const d = this.shadowRoot.querySelector("dialog");
    d.querySelector("h3").textContent = title;
    d.querySelector(".dialog-body").innerHTML = html;
    d.showModal();
  }
  async _save() {
    const selected = this._selected,
      ids = [...this._selection],
      bulk = this._bulk(),
      config = copy(this._drafts.get(selected)),
      patch = copy(this._bulkPatch);
    this._busy = true;
    this._error = "";
    this._render();
    try {
      const msg = bulk
        ? {
            type: "cca_zaluzie/configure_bulk",
            entry_ids: ids,
            patch,
            revisions: copy(this._bulkRevisions),
          }
        : {
            type: "cca_zaluzie/configure",
            entry_id: selected,
            config,
            ...(this._draftRevisions.get(selected)
              ? { expected_revision: this._draftRevisions.get(selected) }
              : {}),
          };
      const r = await this.hass.callWS(msg);
      if (!r?.saved) throw Error("Uloženie sa nepotvrdilo.");
      for (const id of bulk ? ids : [selected]) {
        const saved = bulk ? r.configs[id] : r.config || config;
        const oldDraft = this._drafts.get(id),
          oldBase = this._draftBases.get(id);
        const local =
          bulk && this._dirty.has(id)
            ? Object.fromEntries(
                Object.entries(oldDraft).filter(
                  ([key, value]) =>
                    JSON.stringify(value) !== JSON.stringify(oldBase?.[key]) &&
                    !Object.hasOwn(patch, key),
                ),
              )
            : {};
        this._baseline.set(id, copy(saved));
        this._draftBases.set(id, copy(saved));
        this._drafts.set(id, { ...copy(saved), ...copy(local) });
        if (Object.keys(local).length) this._dirty.add(id);
        else this._dirty.delete(id);
        const c = this._controllers.get(id);
        if (c) {
          c.config = copy(saved);
          c.name = saved.name;
        }
        const revision = bulk ? r.config_revisions?.[id] : r.config_revision;
        if (revision) this._draftRevisions.set(id, revision);
        else if (!Object.keys(local).length) this._draftRevisions.delete(id);
      }
      this._bulkPatch = {};
      this._bulkRevisions = {};
      this._notify(
        bulk
          ? `Uložené: ${ids.length} automatizácie · ${Object.keys(patch).length} polí.`
          : "Nastavenia uložené v Home Assistante.",
      );
      const data = await this.hass.callWS({ type: "cca_zaluzie/list" });
      for (const c of data.controllers) {
        this._update(c);
      }
    } catch (e) {
      this._error = e.message || String(e);
    } finally {
      this._busy = false;
      this._render();
    }
  }
  async _control(action, position) {
    const id = this._selected;
    this._busy = true;
    this._error = "";
    this._render();
    try {
      const c = await this.hass.callWS({
        type: "cca_zaluzie/control",
        entry_id: id,
        action,
        ...(position != null ? { position } : {}),
      });
      this._update(c);
    } catch (e) {
      this._error = e.message || String(e);
    } finally {
      this._busy = false;
      this._render();
      this._loadHistory();
    }
  }
  async _reorder(id, index) {
    if (this._ordering) return;
    const order = this._order.filter((x) => x !== id);
    order.splice(Math.max(0, Math.min(index, order.length)), 0, id);
    if (order.join() === this._order.join()) return;
    this._ordering = true;
    try {
      const r = await this.hass.callWS({
        type: "cca_zaluzie/reorder",
        entry_ids: order,
        revision: this._orderRevision,
      });
      this._applyOrder(r.order, r.order_revision);
      this._renderList();
      this.shadowRoot.querySelector(`[data-grip="${CSS.escape(id)}"]`)?.focus();
    } catch (e) {
      this._error = e.message || String(e);
      this._render();
    } finally {
      this._ordering = false;
    }
  }
  _toggleSelection(id) {
    if (this._busy) return;
    if (this._selection.has(id)) {
      if (id !== this._selected) this._selection.delete(id);
    } else this._selection.add(id);
    this._bulkPatch = {};
    this._bulkRevisions = {};
    this._render();
  }
  _input(event) {
    const input = event.target;
    if (input.hasAttribute("data-simulation-filter")) {
      if (event.type === "change") {
        this._simulationFilter = input.value;
        this._render();
        this.shadowRoot.querySelector(".simulation-trace").open = true;
      }
      return;
    }
    if (input.hasAttribute("data-position")) {
      const output = input.parentElement.querySelector("output");
      if (output) output.textContent = `${input.value} %`;
      for (const peer of this.shadowRoot.querySelectorAll("[data-position]"))
        if (peer !== input) peer.value = input.value;
      if (
        event.type === "change" &&
        input.value !== "" &&
        Number(input.value) >= 0 &&
        Number(input.value) <= 100
      )
        this._control("position", Number(input.value));
      return;
    }
    if (input.hasAttribute("data-multi")) {
      if (event.type === "change") this._toggleSelection(input.dataset.multi);
      return;
    }
    if (input.hasAttribute("data-history")) {
      if (event.type === "change") {
        this._historyHours = Number(input.value);
        this._render();
        this._loadHistory();
      }
      return;
    }
    if (input.dataset.durationUnit) {
      if (event.type === "change") {
        this._durationUnits ||= {};
        this._durationUnits[input.dataset.durationUnit] = Number(input.value);
        this._render();
      }
      return;
    }
    const key = input.dataset.key,
      f = this._fields?.[key];
    if (!f || this._disabled(f, this._config())) return;
    let value =
      event.type === "value-changed" ? event.detail.value : input.value;
    if (f.kind === "bool") value = input.checked;
    else if (input.dataset.choice) {
      const values = new Set(this._config()[key] || []);
      if (input.checked) values.add(input.dataset.choice);
      else values.delete(input.dataset.choice);
      value = [...values];
    } else if (f.kind === "number") {
      if (input.tagName === "HA-DURATION-INPUT") {
        const data = event.detail?.value || event.detail?.data || input.data;
        value =
          Number(data?.days || 0) * 86400 +
          Number(data?.hours || 0) * 3600 +
          Number(data?.minutes || 0) * 60 +
          Number(data?.seconds || 0);
      } else value = Number(value) * Number(input.dataset.duration || 1);
    }
    if (this._bulk()) {
      if (!f.bulk_editable) return;
      if (!Object.keys(this._bulkRevisions).length)
        this._bulkRevisions = Object.fromEntries(
          [...this._selection].map((id) => [
            id,
            this._controllers.get(id).config_revision,
          ]),
        );
      this._bulkPatch[key] = value;
    } else {
      const cfg = this._drafts.get(this._selected);
      cfg[key] = value;
      if (key === "position_source") cfg.position_source_auto = false;
      this._dirty.add(this._selected);
    }
    const state = this.shadowRoot.querySelector(".draft-state");
    if (state)
      state.textContent = this._bulk()
        ? `${Object.keys(this._bulkPatch).length} výslovne upravených polí`
        : "Neuložené zmeny · iba táto žalúzia";
    for (const other of this.shadowRoot.querySelectorAll(
      `[data-key="${key}"]`,
    )) {
      if (other === input) continue;
      if (f.kind === "number") other.value = value;
    }
    for (const dep of Object.values(this._fields).filter(
      (f) => f.depends === key,
    ))
      for (const el of this.shadowRoot.querySelectorAll(
        `[data-key="${dep.key}"]`,
      ))
        el.disabled = Boolean(this._disabled(dep, this._config()));
    if (input.hasAttribute("data-entity-search")) {
      const results = this.shadowRoot.querySelector(`[data-results="${key}"]`);
      const q = String(value).toLocaleLowerCase();
      results.innerHTML = Object.entries(this.hass.states || {})
        .filter(([id, s]) =>
          `${id} ${s.attributes?.friendly_name || ""}`
            .toLocaleLowerCase()
            .includes(q),
        )
        .slice(0, 30)
        .map(([id, s]) =>
          button(
            `${esc(s.attributes?.friendly_name || id)}<small>${esc(id)}</small>`,
            `data-entity-value="${esc(id)}" data-entity-key="${key}"`,
            "Vybrať túto entitu",
            "entity-result",
          ),
        )
        .join("");
      results.hidden = false;
    }
  }
  async _event(event) {
    if (["input", "change", "value-changed"].includes(event.type)) {
      this._input(event);
      return;
    }
    const target = event.target.closest("[data-grip]");
    if (
      event.type === "keydown" &&
      event.target.hasAttribute("data-measurement") &&
      ["Enter", " "].includes(event.key)
    ) {
      event.preventDefault();
      this._dialog(
        "Nameraná poloha",
        `<p>${esc(new Date(event.target.dataset.pointAt).toLocaleString("sk-SK"))} · ${esc(event.target.dataset.pointPosition)} %</p>`,
      );
      return;
    }
    if (
      event.type === "click" &&
      event.target.hasAttribute("data-measurement")
    ) {
      this._dialog(
        "Nameraná poloha",
        `<p>${esc(new Date(event.target.dataset.pointAt).toLocaleString("sk-SK"))} · ${esc(event.target.dataset.pointPosition)} %</p>`,
      );
      return;
    }
    if (event.type === "keydown") {
      if (
        target &&
        ["ArrowUp", "ArrowDown", "Home", "End"].includes(event.key)
      ) {
        event.preventDefault();
        const id = target.dataset.grip;
        this._reorder(
          id,
          event.key === "Home"
            ? 0
            : event.key === "End"
              ? this._order.length - 1
              : this._order.indexOf(id) + (event.key === "ArrowUp" ? -1 : 1),
        );
      }
      return;
    }
    if (event.type === "dragstart") {
      if (!target) {
        event.preventDefault();
        return;
      }
      this._dragId = target.dataset.grip;
      event.dataTransfer.setData("text/plain", this._dragId);
      event.dataTransfer.effectAllowed = "move";
      return;
    }
    if (["dragover", "drop", "dragleave", "dragend"].includes(event.type)) {
      const row = event.target.closest("[data-row]");
      if (event.type === "dragover" && row && this._dragId) {
        event.preventDefault();
        this.shadowRoot
          .querySelectorAll(".drop-target")
          .forEach((e) => e.classList.remove("drop-target"));
        row.classList.add("drop-target");
        row.classList.toggle(
          "drop-after",
          this._order.indexOf(this._dragId) <
            this._order.indexOf(row.dataset.row),
        );
      }
      if (event.type === "drop" && row && this._dragId) {
        event.preventDefault();
        this._reorder(this._dragId, this._order.indexOf(row.dataset.row));
      }
      if (event.type !== "dragover") {
        row?.classList.remove("drop-target", "drop-after");
        if (event.type !== "dragleave") this._dragId = null;
      }
      return;
    }
    if (event.type !== "click") return;
    const b = event.target.closest("button");
    if (!b || b.disabled) return;
    if (b.dataset.cover) {
      if (event.ctrlKey || event.metaKey) {
        this._toggleSelection(b.dataset.cover);
        return;
      }
      if (this._busy) return;
      this._selected = b.dataset.cover;
      this._selection = new Set([this._selected]);
      this._bulkPatch = {};
      this._bulkRevisions = {};
      this._error = "";
      this._render();
      this._loadHistory();
      return;
    }
    if (b.dataset.grip) return;
    if (b.dataset.order) {
      this._reorder(
        b.dataset.order,
        this._order.indexOf(b.dataset.order) + Number(b.dataset.delta),
      );
      return;
    }
    if (b.hasAttribute("data-clear-selection")) {
      this._selection = new Set([this._selected]);
      this._bulkPatch = {};
      this._bulkRevisions = {};
      this._render();
      return;
    }
    if (b.dataset.view) {
      this._view = b.dataset.view;
      this._render();
      return;
    }
    if (b.dataset.group) {
      this._group = b.dataset.group;
      this._render();
      return;
    }
    if (b.hasAttribute("data-dialog-close")) {
      this.shadowRoot.querySelector("dialog").close();
      return;
    }
    if (b.hasAttribute("data-dismiss")) {
      this._notice = "";
      this.shadowRoot.querySelector(".toast")?.remove();
      return;
    }
    if (b.dataset.help) {
      const f = this._fields[b.dataset.help];
      this._dialog(
        f.label,
        `<p>${esc(f.help || `Nastaviť ${f.label.toLocaleLowerCase("sk")}. Zmena sa použije po uložení.`)}</p>`,
      );
      return;
    }
    if (b.dataset.entityValue) {
      const input = this.shadowRoot.querySelector(
        `[data-key="${b.dataset.entityKey}"]`,
      );
      input.value = b.dataset.entityValue;
      this._input({ target: input, type: "change" });
      this.shadowRoot.querySelector(
        `[data-results="${b.dataset.entityKey}"]`,
      ).hidden = true;
      return;
    }
    if (b.hasAttribute("data-explanation")) {
      const c = this._controllers.get(this._selected);
      this._dialog(
        "Podmienky a vstupy",
        `<pre>${esc(JSON.stringify(c.explanation?.details || c.decision?.conditions || {}, null, 2))}</pre>`,
      );
      return;
    }
    if (b.dataset.event) {
      const c = this._controllers.get(this._selected),
        h = this._history.get(`${this._selected}:${this._historyHours}`);
      const e = [...(c.events || []), ...(h?.events || [])].find(
        (e) => e.id === b.dataset.event,
      );
      if (e)
        this._dialog(
          eventNames[e.type] || e.type,
          `<pre>${esc(JSON.stringify({ čas: e.at, ...e.details }, null, 2))}</pre>`,
        );
      return;
    }
    if (b.hasAttribute("data-discard")) {
      if (this._bulk()) {
        this._bulkPatch = {};
        this._bulkRevisions = {};
      } else {
        this._drafts.set(
          this._selected,
          copy(this._baseline.get(this._selected)),
        );
        this._dirty.delete(this._selected);
        this._draftBases.set(
          this._selected,
          copy(this._baseline.get(this._selected)),
        );
        this._draftRevisions.set(
          this._selected,
          this._controllers.get(this._selected)?.config_revision,
        );
      }
      this._error = "";
      this._render();
      return;
    }
    if (b.hasAttribute("data-save")) {
      if (this._bulk()) {
        const keys = Object.keys(this._bulkPatch);
        if (!keys.length) {
          this._notify("Najprv uprav povolené pole.");
          this._render();
          return;
        }
        this._dialog(
          "Potvrdiť hromadnú úpravu",
          `<p>Uložiť ${keys.length} upravených polí pre ${this._selection.size} automatizácie?</p><ul>${keys.map((k) => `<li>${esc(this._fields[k].label)}: ${esc(this._format(this._fields[k], this._bulkPatch[k]))}</li>`).join("")}</ul>${button("Potvrdiť hromadné uloženie", "data-confirm-bulk", "Uložiť iba uvedené polia všetkých vybraných automatizácií.", "btn primary")}`,
        );
      } else this._save();
      return;
    }
    if (b.hasAttribute("data-confirm-bulk")) {
      this._save();
      return;
    }
    if (b.hasAttribute("data-reset")) {
      this._dialog(
        "Reset polohy",
        `<p>Žalúzia sa úplne zatvorí, po potvrdení dorazu zostane 60 sekúnd na doraze a následne dostane STOP. Prerušený reset nebude označený za úspešný.</p>${button("Spustiť reset", 'data-action="reset"', "Potvrdiť úplné zatvorenie a reset polohy.", "btn primary")}`,
      );
      return;
    }
    if (b.dataset.action) this._control(b.dataset.action);
  }
  _countdown() {
    for (const el of this.shadowRoot.querySelectorAll("[data-due]")) {
      const left = Math.max(
        0,
        Math.ceil(
          Number(el.dataset.due) - Date.now() / 1000 - (this._offset || 0),
        ),
      );
      el.textContent = Number(el.dataset.due)
        ? `${String(Math.floor(left / 60)).padStart(2, "0")}:${String(left % 60).padStart(2, "0")}`
        : "…";
    }
  }
}
if (!customElements.get("cca-zaluzie-panel"))
  customElements.define("cca-zaluzie-panel", CCAZaluziePanel);
