import * as Plot from "https://cdn.jsdelivr.net/npm/@observablehq/plot@0.6.16/+esm";
import { enhanceTables } from "./tables.js";
import { formatPerResident, truncate } from "./format.js";
import { KINDS, parsePeerHash, serializePeerHash, visibleGroups, groupStats, headline, fiscalYearEnd, rankLabel, cityMatrix, yearView, trendSeries } from "./peers-model.js";

const $ = (id) => document.getElementById(id);
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

const REGIONS = ["West", "South", "Midwest", "Pacific Northwest", "Northeast"];
const REGION_COLORS = ["#E69F00", "#56B4E9", "#009E73", "#CC79A7", "#D55E00"];

let data;
try {
  const response = await fetch("data/peers.json");
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  data = await response.json();
} catch (error) {
  $("phead").textContent = "Sorry, the city comparison data could not be loaded. Please try again later.";
  throw error;
}

const YEARS = data.years.map((y) => y.fiscal_year).sort((a, b) => b - a);
const LATEST = YEARS[0];

// Hash values the page cannot honour (an unknown year or service) quietly fall back to the defaults.
function sanitize(parsed) {
  const groups = visibleGroups(data, parsed.kinds);
  return {
    kinds: parsed.kinds, adjusted: parsed.adjusted,
    year: YEARS.includes(parsed.year) && parsed.year !== LATEST ? parsed.year : null,
    trend: groups.some((g) => g.key === parsed.trend) ? parsed.trend : "all",
  };
}

let state = sanitize(parsePeerHash(location.hash));

function readControls() {
  return sanitize({
    kinds: KINDS.filter((k) => $(`kind-${k}`).checked),
    adjusted: $("adjust").checked,
    year: Number($("year").value),
    trend: $("trend-service").value,
  });
}

function update() {
  state = readControls();
  history.replaceState(null, "", serializePeerHash(state) || location.pathname + location.search);
  render();
}

function fillTable(tableId, lines) {
  $(tableId).querySelector("tbody").replaceChildren(...lines.map((cells) => {
    const tr = document.createElement("tr");
    for (const cell of cells) {
      const td = document.createElement("td");
      td.textContent = cell;
      tr.append(td);
    }
    return tr;
  }));
}

function drawChart(stats) {
  const width = Math.max(300, $("peer-chart").clientWidth);
  const marginLeft = Math.round(Math.min(230, Math.max(110, width * 0.3)));
  const labels = stats.map((s) => s.label);
  const peers = stats.flatMap((s) => s.values.filter((v) => !v.is_home && v.per_resident > 0).map((v) => ({ ...v, label: s.label })));
  const home = stats.filter((s) => !s.homeIsZero).map((s) => ({ label: s.label, per_resident: s.home.per_resident }));
  const mids = stats.filter((s) => s.median !== null).map((s) => ({ label: s.label, per_resident: s.median }));
  $("peer-chart").replaceChildren(Plot.plot({
    width, height: 38 * labels.length + 50, marginLeft, marginRight: 20,
    x: { label: null, grid: true, ticks: width < 500 ? 3 : 6, tickFormat: (v) => formatPerResident(v) },
    y: { label: null, type: "band", padding: 0.3, domain: labels, tickFormat: (n) => truncate(n, Math.floor(marginLeft / 6.6)) },
    color: { domain: REGIONS, range: REGION_COLORS },
    marks: [
      Plot.dot(peers, { x: "per_resident", y: "label", fill: "region", r: 5, fillOpacity: 0.85,
        title: (d) => `${d.city}: ${formatPerResident(d.per_resident)} per resident` }),
      Plot.dot(home, { x: "per_resident", y: "label", r: 8, fill: css("--accent"), stroke: css("--bg"), strokeWidth: 2,
        title: (d) => `San Diego: ${formatPerResident(d.per_resident)} per resident` }),
      Plot.tickX(mids, { x: "per_resident", y: "label", stroke: css("--text"), strokeWidth: 3,
        title: (d) => `Middle peer: ${formatPerResident(d.per_resident)} per resident` }),
      Plot.ruleX([0]),
    ],
  }));
}

// Inline styles on purpose: the legend must still make sense if the browser holds an older cached site.css.
function drawLegend() {
  const swatch = (style) => `<span class="swatch" style="display:inline-block;width:.8rem;height:.8rem;margin-right:.3rem;vertical-align:-1px;${style}"></span>`;
  const items = [
    `${swatch(`background:${css("--accent")};border-radius:50%`)}San Diego`,
    `${swatch(`width:3px;height:1rem;margin:0 .45rem 0 .15rem;background:${css("--text")}`)}Middle peer`,
    ...REGIONS.map((r, i) => `${swatch(`background:${REGION_COLORS[i]};border-radius:50%`)}${r}`),
  ];
  $("peer-legend").style.cssText = "display:flex;flex-wrap:wrap;gap:.25rem 1rem;padding:0;list-style:none;font-size:.85rem";
  $("peer-legend").innerHTML = items.map((html) => `<li>${html}</li>`).join("");
}

function drawMatrix({ columns, rows }) {
  const head = document.createElement("tr");
  for (const label of ["City", ...columns.map((c) => c.label)]) {
    const th = document.createElement("th");
    th.scope = "col";
    th.textContent = label;
    head.append(th);
  }
  $("matrix-table").querySelector("thead").replaceChildren(head);
  $("matrix-table").querySelector("tbody").replaceChildren(...rows.map((row) => {
    const tr = document.createElement("tr");
    const th = document.createElement("th");
    th.scope = "row";
    th.textContent = row.city;
    tr.append(th);
    for (const value of row.values) {
      const td = document.createElement("td");
      td.textContent = formatPerResident(value);
      tr.append(td);
    }
    return tr;
  }));
}

function sentence(value) {
  return value === null ? "n/a" : formatPerResident(value);
}

function gap(pct) {
  if (pct === null) return "n/a";
  const rounded = Math.round(pct);
  return rounded === 0 ? "0%" : `${rounded > 0 ? "+" : "−"}${Math.abs(rounded)}%`;
}

const TREND_LINES = [
  { key: "pct", label: "As reported", color: () => css("--text"), dash: "5 4" },
  { key: "pctAdjusted", label: "Adjusted for local prices", color: () => css("--accent"), dash: null },
];

function drawTrend(series) {
  const width = Math.max(300, $("trend-chart").clientWidth);
  const points = TREND_LINES.flatMap((line) => series.filter((r) => r[line.key] !== null)
    .map((r) => ({ year: r.fiscal_year, pct: r[line.key], line: line.label })));
  $("trend-chart").replaceChildren(Plot.plot({
    width, height: 260, marginLeft: 56, marginRight: 20,
    x: { label: null, ticks: YEARS.length, tickFormat: (v) => String(v), type: "linear", domain: [Math.min(...YEARS) - 0.2, LATEST + 0.2] },
    y: { label: "Gap to the middle peer (%)", grid: true, tickFormat: (v) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v)}%` },
    color: { domain: TREND_LINES.map((l) => l.label), range: TREND_LINES.map((l) => l.color()) },
    marks: [
      Plot.ruleY([0]),
      Plot.line(points, { x: "year", y: "pct", stroke: "line", strokeWidth: 2 }),
      Plot.dot(points, { x: "year", y: "pct", fill: "line", r: 4, title: (d) => `${d.line}, ${d.year}: ${gap(d.pct)}` }),
    ],
  }));
  const swatch = (color) => `<span class="swatch" style="display:inline-block;width:1.2rem;height:3px;margin-right:.4rem;vertical-align:middle;background:${color}"></span>`;
  $("trend-legend").style.cssText = "display:flex;flex-wrap:wrap;gap:.25rem 1rem;padding:0;list-style:none;font-size:.85rem";
  $("trend-legend").innerHTML = TREND_LINES.map((l) => `<li>${swatch(l.color())}${l.label}</li>`).join("");
}

function fillTrendOptions() {
  const groups = visibleGroups(data, state.kinds);
  const options = [["all", "All the services included above"], ...groups.map((g) => [g.key, g.label])];
  $("trend-service").replaceChildren(...options.map(([value, label]) => new Option(label, value)));
  $("trend-service").value = state.trend;
}

function render() {
  for (const kind of KINDS) $(`kind-${kind}`).checked = state.kinds.includes(kind);
  $("adjust").checked = state.adjusted;
  $("year").value = String(state.year ?? LATEST);
  $("adjust-note").hidden = !state.adjusted;
  fillTrendOptions();
  const view = yearView(data, state.year ?? LATEST, state.adjusted);
  const text = headline(view, state.kinds, state.adjusted);
  if ($("phead").textContent !== text) $("phead").textContent = text;
  drawTrend(trendSeries(data, state.kinds, state.trend));
  fillTable("trend-table", trendSeries(data, state.kinds, state.trend).map((r) => [
    String(r.fiscal_year), sentence(r.home), sentence(r.middle), gap(r.pct),
    sentence(r.homeAdjusted), sentence(r.middleAdjusted), gap(r.pctAdjusted),
  ]));
  const stats = visibleGroups(view, state.kinds).map((g) => groupStats(view, g.key));
  drawChart(stats);
  drawLegend();
  fillTable("peer-table", stats.map((s) => [
    s.label,
    s.homeIsZero ? "$0 (not provided by the city)" : formatPerResident(s.home.per_resident),
    s.median === null ? "n/a" : formatPerResident(s.median),
    s.min === null ? "n/a" : `${formatPerResident(s.min)} to ${formatPerResident(s.max)}`,
    rankLabel(s.rank, s.of),
    s.zeroCities.join(", ") || "none",
  ]));
  drawMatrix(cityMatrix(view, state.kinds));
  $("city-caption").textContent = `Population and the fiscal year that ended, as reported to the Census. The ${view.fiscal_year} survey covers years that ended between July ${view.fiscal_year - 1} and June ${view.fiscal_year}, so cities with a September or December year end show ${view.fiscal_year - 1}.`;
  fillTable("city-table", view.cities.map((c) => [
    c.city, c.region, c.population.toLocaleString("en-US"), fiscalYearEnd(c.fy_end, view.fiscal_year),
  ]));
}

$("year").replaceChildren(...YEARS.map((y) => new Option(String(y), String(y))));
for (const id of [...KINDS.map((k) => `kind-${k}`), "adjust", "year", "trend-service"]) $(id).addEventListener("change", update);
window.addEventListener("hashchange", () => { state = sanitize(parsePeerHash(location.hash)); render(); });
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);

let lastWidth = $("peer-chart").clientWidth;
new ResizeObserver(() => {
  const width = $("peer-chart").clientWidth;
  if (width !== lastWidth) { lastWidth = width; render(); }
}).observe($("peer-chart"));

render();

enhanceTables();
