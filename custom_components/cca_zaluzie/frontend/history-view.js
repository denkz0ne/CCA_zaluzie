/* Read-only history presentation. Solar height and cover position share time, not units. */
const stamp = (value) =>
  typeof value === "number" ? value * 1000 : Date.parse(value);
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );

export function mergedEvents(controller, history) {
  return [
    ...new Map(
      [...(history?.events || []), ...(controller.events || [])].map((e) => [
        e.id,
        e,
      ]),
    ).values(),
  ].sort((a, b) => stamp(a.at) - stamp(b.at));
}

export function usefulEvents(events) {
  let previous;
  const result = [];
  for (const event of events) {
    if (event.simulated) continue;
    if (event.type === "decision") {
      const d = event.details || {},
        signature = JSON.stringify([d.mode || null, d.inhibit || null]);
      if (previous !== undefined && signature !== previous) {
        const label = d.inhibit
          ? "Ochrana alebo blokácia"
          : "Zmena režimu riadenia";
        result.push({ ...event, overviewLabel: label });
      }
      previous = signature;
    } else if (
      !["reconcile", "command_requested", "drive_pending"].includes(event.type)
    )
      result.push(event);
  }
  return result.slice(-20).reverse();
}

export function historyChart(controller, history, start, end, points) {
  const left = 24,
    width = 1052,
    horizon = 127;
  const x = (at) =>
    left +
    Math.max(0, Math.min(1, (stamp(at) - start) / (end - start))) * width;
  const y = (value) => horizon - Math.max(0, Math.min(100, value)) * 0.95;
  let path = "",
    previous = null,
    gap = false;
  for (const point of points) {
    const at = stamp(point.at),
      valid =
        point.available &&
        Number.isFinite(point.position) &&
        point.position >= 0 &&
        point.position <= 100;
    if (!Number.isFinite(at)) continue;
    if (at < start) {
      previous = valid ? point : null;
      continue;
    }
    if (at > end) break;
    if (!valid) {
      if (previous) {
        if (stamp(previous.at) < start)
          path += ` M ${left} ${y(previous.position)}`;
        path += ` H ${x(point.at)}`;
      }
      previous = null;
      gap = true;
      continue;
    }
    if (previous) {
      if (stamp(previous.at) < start)
        path += ` M ${left} ${y(previous.position)}`;
      // Sparse state changes do not prove a motor moved throughout the whole interval.
      path +=
        at - stamp(previous.at) <= 180000
          ? ` L ${x(point.at)} ${y(point.position)}`
          : ` H ${x(point.at)} V ${y(point.position)}`;
    } else path += ` M ${x(point.at)} ${y(point.position)}`;
    previous = point;
  }
  if (
    previous &&
    controller.available &&
    Number.isFinite(controller.position)
  ) {
    if (stamp(previous.at) < start)
      path += ` M ${left} ${y(previous.position)}`;
    path += ` H ${left + width}`;
  }
  const solar = (history?.solar || []).filter(
    (p) => Number.isFinite(p.elevation) && Number.isFinite(stamp(p.at)),
  );
  const positive = Math.max(1, ...solar.map((p) => p.elevation));
  const negative = Math.max(1, ...solar.map((p) => -p.elevation));
  // One linear scale preserves the solar curve, fitted to the available space.
  const scale = Math.min(95 / positive, 125 / negative);
  const sun = solar
    .map(
      (p, i) => `${i ? "L" : "M"} ${x(p.at)} ${horizon - p.elevation * scale}`,
    )
    .join(" ");
  const area = solar.length
    ? `${sun} L ${x(solar.at(-1).at)} ${horizon} L ${x(solar[0].at)} ${horizon} Z`
    : "";
  const id = `history-${String(controller.entry_id).replace(/[^a-zA-Z0-9_-]/g, "")}`;
  const timeZone = history?.time_zone;
  const time = (at) =>
    new Date(at).toLocaleTimeString("sk-SK", {
      hour: "2-digit",
      minute: "2-digit",
      ...(timeZone ? { timeZone } : {}),
    });
  const labels = Array.from({ length: 5 }, (_, i) => {
    const at = start + ((end - start) * i) / 4;
    return `<text x="${left + (width * i) / 4}" y="277" text-anchor="${i === 0 ? "start" : i === 4 ? "end" : "middle"}">${esc(time(at))}</text>`;
  }).join("");
  const crossings = solar
    .filter(
      (p) => p.elevation === 0 && stamp(p.at) >= start && stamp(p.at) <= end,
    )
    .map((p) => {
      const i = solar.indexOf(p),
        rising = solar[i + 1]?.elevation > 0;
      return `<line x1="${x(p.at)}" x2="${x(p.at)}" y1="120" y2="134" class="solar-crossing"/><text x="${Math.min(left + width - 45, x(p.at) + 7)}" y="148" class="solar-caption">${rising ? "Východ" : "Západ"}</text>`;
    })
    .join("");
  return `<div class="simple-chart"><svg viewBox="0 0 1100 286" role="img" aria-label="História polohy žalúzie a orientačná krivka dňa a noci na spoločnej časovej osi. Žltá nad nulou je deň, modrá pod nulou noc."><defs><clipPath id="${id}-day"><rect x="24" y="15" width="1052" height="112"/></clipPath><clipPath id="${id}-night"><rect x="24" y="127" width="1052" height="129"/></clipPath></defs><path class="solar-day-fill" d="${area}" clip-path="url(#${id}-day)"/><path class="solar-night-fill" d="${area}" clip-path="url(#${id}-night)"/><line x1="24" x2="1076" y1="127" y2="127" class="solar-horizon"/><path class="solar-day-line" d="${sun}" clip-path="url(#${id}-day)"/><path class="solar-night-line" d="${sun}" clip-path="url(#${id}-night)"/><path class="measured-line" d="${path}"/><text x="15" y="131" text-anchor="end">0</text>${crossings}${labels}</svg></div>${history?.error ? `<p class="history-gap">História nie je dostupná: ${esc(history.error)}</p>` : !points.some((p) => p.available && Number.isFinite(p.position)) ? '<p class="history-gap">Zatiaľ nie sú dostupné namerané údaje.</p>' : gap ? '<p class="history-gap">Medzera v čiare znamená chýbajúcu alebo nedostupnú polohu.</p>' : ""}${!solar.length ? '<p class="history-gap">Krivka slnka zatiaľ nie je dostupná.</p>' : ""}`;
}
