/* Render the approved day/night/shutter concept from editable vector geometry. */
import { mkdir, writeFile } from "node:fs/promises";
import { chromium } from "playwright";

const brand = "custom_components/cca_zaluzie/brand";
const frontend = "custom_components/cca_zaluzie/frontend";
const n = (v) => Number(v.toFixed(3));
const polygon = (points) => {
  const area = points.reduce((sum, p, i) => {
    const q = points[(i + 1) % points.length];
    return sum + p[0] * q[1] - q[0] * p[1];
  }, 0);
  // Holes run opposite the clockwise outer circle (nonzero HA SVG fill rule).
  if (area > 0) points.reverse();
  return (
    points.map((p, i) => `${i ? "L" : "M"}${n(p[0])} ${n(p[1])}`).join(" ") +
    "Z"
  );
};
const rect = (x, y, w, h) =>
  polygon([
    [x, y],
    [x + w, y],
    [x + w, y + h],
    [x, y + h],
  ]);
const roundedRect = (x, y, w, h, r) => {
  const points = [];
  for (const [cx, cy, start] of [
    [x + w - r, y + r, -90],
    [x + w - r, y + h - r, 0],
    [x + r, y + h - r, 90],
    [x + r, y + r, 180],
  ])
    for (let i = 0; i <= 8; i++) {
      const a = ((start + (i * 90) / 8) * Math.PI) / 180;
      points.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]);
    }
  return polygon(points);
};
const circle = (cx, cy, r) =>
  `M${cx + r} ${cy}a${r} ${r} 0 1 0 ${-2 * r} 0a${r} ${r} 0 1 0 ${2 * r} 0Z`;
const sun = circle(78, 80, 23);
const rays = [];
for (let i = 0; i < 8; i++) {
  const a = (i * Math.PI) / 4;
  const points = [];
  for (let j = 0; j < 20; j++) {
    const t = (2 * Math.PI * j) / 20;
    // Capsule: radius3, straight length5, center radius34 from the sun.
    const u = 34 + Math.cos(t) * 3 + (Math.cos(t) >= 0 ? 2.5 : -2.5);
    const v = Math.sin(t) * 3;
    points.push([
      78 + u * Math.cos(a) - v * Math.sin(a),
      80 + u * Math.sin(a) + v * Math.cos(a),
    ]);
  }
  rays.push(polygon(points));
}
// Crescent formed by two intersecting circular arcs, no tiny separate overlay.
const moonPoints = [];
for (let i = 0; i <= 48; i++) {
  const a = ((-70 - (i * 265) / 48) * Math.PI) / 180;
  moonPoints.push([180 + 31 * Math.cos(a), 78 + 31 * Math.sin(a)]);
}
const end = moonPoints.at(-1),
  start = moonPoints[0];
// Quadratic inner edge joins the same endpoints and curves toward the left.
for (let i = 1; i <= 32; i++) {
  const t = i / 32,
    u = 1 - t;
  moonPoints.push([
    u * u * end[0] + 2 * u * t * 143 + t * t * start[0],
    u * u * end[1] + 2 * u * t * 72 + t * t * start[1],
  ]);
}
const moon = polygon(moonPoints);
const white = [
  sun,
  ...rays,
  moon,
  rect(16, 125, 224, 6),
  roundedRect(52, 160, 152, 19, 5),
  roundedRect(52, 193, 152, 19, 5),
].join(" ");
const outline = "M128 16a112 112 0 1 1 0 224a112 112 0 1 1 0-224Z";
const monoPath = outline + " " + white + " " + rect(125, 16, 6, 109);
const colorSvg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256"><title>CCA Žalúzie — deň a noc</title><defs><clipPath id="disc"><circle cx="128" cy="128" r="112"/></clipPath></defs><g clip-path="url(#disc)"><circle cx="128" cy="128" r="112" fill="#18BCF2"/><path d="M16 16H128V128H16Z" fill="#FFC857"/><path d="M128 16H240V128H128Z" fill="#123C55"/><path d="${white}" fill="#fff"/></g></svg>\n`;
const monoSvg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256"><title>CCA Žalúzie</title><path fill="currentColor" d="${monoPath}"/></svg>\n`;
await mkdir(brand, { recursive: true });
await writeFile(`${brand}/icon.svg`, colorSvg);
await writeFile(`${frontend}/icon.svg`, monoSvg);
await writeFile(
  `${frontend}/icons.js`,
  `/* Theme-aware monochrome icon, loaded globally before sidebar rendering. */\nexport const iconPath = ${JSON.stringify(monoPath)};\nwindow.customIcons = window.customIcons || {};\nwindow.customIcons.cca = {\n  getIcon: async (name) => name === "day-night-blinds" ? {path: iconPath, viewBox: "0 0 256 256"} : {path: ""},\n  getIconList: async () => [{name: "day-night-blinds", keywords: ["blinds", "day", "night", "žalúzie"]}],\n};\n`,
);
const browser = await chromium.launch();
const page = await browser.newPage();
for (const [size, name] of [
  [256, "icon.png"],
  [512, "icon@2x.png"],
]) {
  await page.setViewportSize({ width: size, height: size });
  await page.setContent(
    `<style>html,body{margin:0;background:transparent}svg{width:100vw;height:100vh;display:block}</style>${colorSvg}`,
  );
  await page.screenshot({ path: `${brand}/${name}`, omitBackground: true });
}
await browser.close();
console.log("Built color SVG/PNG and matching monochrome HA icon.");
