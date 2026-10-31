import * as Plot from "https://cdn.jsdelivr.net/npm/@observablehq/plot@0.6.16/+esm";
import { enhanceTables } from "./tables.js";
import { formatPerResident, truncate } from "./format.js";
import { KINDS, parsePeerHash, serializePeerHash, visibleGroups, groupStats, headline, fiscalYearEnd, rankLabel, cityMatrix } from "./peers-model.js";

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

let state = parsePeerHash(location.hash);

function update(kinds) {
  state = parsePeerHash(serializePeerHash({ kinds: KINDS.filter((k) => kinds.includes(k)) }));
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

function drawLegend() {
  const items = [
    `<li><span class="swatch" style="background:${css("--accent")}"></span>San Diego</li>`,
    `<li><span class="swatch" style="width:3px;height:1rem;margin:0 .45rem 0 .15rem;background:${css("--text")}"></span>Middle peer</li>`,
    ...REGIONS.map((r, i) => `<li><span class="swatch" style="background:${REGION_COLORS[i]};border-radius:50%"></span>${r}</li>`),
  ];
  $("peer-legend").innerHTML = items.join("");
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

function render() {
  for (const kind of KINDS) $(`kind-${kind}`).checked = state.kinds.includes(kind);
  const sentence = headline(data, state.kinds);
  if ($("phead").textContent !== sentence) $("phead").textContent = sentence;
  const stats = visibleGroups(data, state.kinds).map((g) => groupStats(data, g.key));
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
  drawMatrix(cityMatrix(data, state.kinds));
  fillTable("city-table", data.cities.map((c) => [
    c.city, c.region, c.population.toLocaleString("en-US"), fiscalYearEnd(c.fy_end, data.fiscal_year),
  ]));
}

for (const kind of KINDS) {
  $(`kind-${kind}`).addEventListener("change", () => update(KINDS.filter((k) => $(`kind-${k}`).checked)));
}
window.addEventListener("hashchange", () => { state = parsePeerHash(location.hash); render(); });
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);

let lastWidth = $("peer-chart").clientWidth;
new ResizeObserver(() => {
  const width = $("peer-chart").clientWidth;
  if (width !== lastWidth) { lastWidth = width; render(); }
}).observe($("peer-chart"));

render();

enhanceTables();
