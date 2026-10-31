import * as Plot from "https://cdn.jsdelivr.net/npm/@observablehq/plot@0.6.16/+esm";
import { enhanceTables } from "./tables.js";
import { formatMoney, truncate } from "./format.js";
import { topVendors, concentration, searchVendors, parseVendorHash, serializeVendorHash } from "./vendors-model.js";

const $ = (id) => document.getElementById(id);
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const money = (n) => `$${Math.round(n).toLocaleString("en-US")}`;

let data;
try {
  const response = await fetch("data/vendors.json");
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  data = await response.json();
} catch (error) {
  $("vhead").textContent = "Sorry, the vendor data could not be loaded. Please try again later.";
  throw error;
}

let state = parseVendorHash(location.hash, data.years);
let selected = null; // vendor whose trend is shown

function update(patch) {
  state = parseVendorHash(serializeVendorHash({ ...state, ...patch }), data.years);
  history.replaceState(null, "", serializeVendorHash(state));
  render();
}

function fillTable(tableId, lines) {
  $(tableId).querySelector("tbody").replaceChildren(...lines.map((cells) => {
    const tr = document.createElement("tr");
    for (const cell of cells) {
      const td = document.createElement("td");
      if (cell instanceof Node) td.append(cell);
      else td.textContent = cell;
      tr.append(td);
    }
    return tr;
  }));
}

function drawLeaders(leaders) {
  const width = Math.max(300, $("leaders").clientWidth);
  const marginLeft = Math.round(Math.min(240, Math.max(110, width * 0.34)));
  $("leaders").replaceChildren(Plot.plot({
    width, height: 24 * leaders.length + 40, marginLeft, marginRight: 64,
    x: { label: null, grid: true, ticks: width < 500 ? 3 : 8, tickFormat: (v) => formatMoney(v) },
    y: { label: null, domain: leaders.map((l) => l.name), tickFormat: (n) => truncate(n, Math.floor(marginLeft / 6.6)) },
    marks: [
      Plot.barX(leaders, { y: "name", x: "amount", fill: css("--accent"), title: (d) => `${d.name}: ${money(d.amount)}` }),
      Plot.text(leaders, { y: "name", x: "amount", text: (d) => formatMoney(d.amount), dx: 4, textAnchor: "start" }),
      Plot.ruleX([0]),
    ],
  }));
}

function drawTrend(vendor) {
  const points = data.years.filter((y) => vendor.amounts[y] !== undefined)
    .map((y) => ({ fy: y, amount: vendor.amounts[y] }));
  $("trend-title").textContent = vendor.name;
  $("trend-figure").hidden = false;
  $("vendor-trend").replaceChildren(Plot.plot({
    width: Math.max(300, $("vendor-trend").clientWidth), height: 200, marginLeft: 56,
    x: { tickFormat: "d", label: null, tickSize: 0, domain: data.years },
    y: { label: null, grid: true, tickFormat: (v) => formatMoney(v) },
    marks: [Plot.barY(points, { x: "fy", y: "amount", fill: css("--accent"), title: (d) => `FY${d.fy}: ${money(d.amount)}` }), Plot.ruleY([0])],
  }));
}

function drawSearch() {
  const matches = searchVendors(data.vendors, state.q, state.fy);
  // only rewrite the box when it differs after trimming, or typing a space would be erased
  if ($("q").value.trim() !== state.q) $("q").value = state.q;
  $("search-table").hidden = matches.length === 0;
  $("search-empty").hidden = state.q === "" || matches.length > 0;
  fillTable("search-table", matches.map((vendor) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "Show trend";
    button.addEventListener("click", () => { selected = vendor; drawTrend(vendor); });
    return [vendor.name, ...data.years.map((y) => (vendor.amounts[y] === undefined ? "—" : formatMoney(vendor.amounts[y]))), button];
  }));
  if (selected && !matches.includes(selected)) {
    selected = null;
    $("trend-figure").hidden = true;
  }
}

function render() {
  $("fy").value = state.fy;
  $("fy-label").textContent = `FY${state.fy}`;
  const conc = concentration(data.vendors, state.fy, 10);
  const cov = data.coverage[state.fy];
  $("vhead").textContent =
    `FY${state.fy}: the City paid ${conc.count.toLocaleString("en-US")} vendors $25,000 or more, ${formatMoney(conc.total)} in total. The 10 largest received ${Math.round(conc.share * 100)}% of that.`;
  const basis = cov.reference_basis === "actual" ? "actual spending" : "adopted budget";
  $("vcoverage").textContent =
    `For scale, the City's FY${state.fy} ${basis} was ${formatMoney(cov.reference_total)}, but the two figures are not directly comparable: the City's figure includes payroll, while this list includes capital, pass-through and other payments. Vendors paid less than $25,000 in the year are not published, so this is not total spending.`;
  const leaders = topVendors(data.vendors, state.fy, 25);
  drawLeaders(leaders);
  fillTable("leader-table", leaders.map((l) => [l.name, money(l.amount), `${((100 * l.amount) / conc.total).toFixed(1)}%`]));
  drawSearch();
  if (selected) drawTrend(selected);
}

$("fy").addEventListener("input", (e) => update({ fy: Number(e.target.value) }));
$("q").addEventListener("input", (e) => update({ q: e.target.value }));
window.addEventListener("hashchange", () => { state = parseVendorHash(location.hash, data.years); render(); });
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);

let lastWidth = $("leaders").clientWidth;
new ResizeObserver(() => {
  const width = $("leaders").clientWidth;
  if (width !== lastWidth) { lastWidth = width; render(); }
}).observe($("leaders"));

render();

enhanceTables();
