import * as Plot from "https://cdn.jsdelivr.net/npm/@observablehq/plot@0.6.16/+esm";
import { enhanceTables } from "./tables.js";
import { formatMoney, formatPerResident } from "./format.js";
import { cityPerCounted, hhapPerCounted, pitIndex, outcomeSeries, parseHomelessHash, serializeHomelessHash, normalizeHomelessState } from "./homelessness-model.js";

const $ = (id) => document.getElementById(id);
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

let data;
try {
  const response = await fetch("data/homelessness.json");
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  data = await response.json();
} catch (error) {
  $("hhead").textContent = "Sorry, the homelessness data could not be loaded. Please try again later.";
  throw error;
}

const NAMES = Object.fromEntries(data.regions.map((r) => [r.coc_id, r.name]));
const ROLE = Object.fromEntries(data.regions.map((r) => [r.coc_id, r.role]));
const PALETTE = ["#E69F00", "#56B4E9", "#009E73", "#CC79A7", "#D55E00", "#0072B2", "#8a8a8a", "#b8860b", "#6a3d9a", "#2f7f7f", "#a65628", "#4d4d4d"];
const colorOf = (id) => ROLE[id] === "home" ? css("--accent") : PALETTE[data.regions.filter((r) => r.role !== "home").findIndex((r) => r.coc_id === id) % PALETTE.length];
const MEASURE_TEXT = {
  exit: { label: "Exited to permanent housing, share of people served", note: "People who exited homelessness into permanent housing during the calendar year, as a share of everyone served that year. Higher is better, but a region that serves more people who are hard to house can score lower.", fmt: (v) => `${(v * 100).toFixed(1)}%` },
  days: { label: "Average days spent homeless", note: "The average length of time people were enrolled in outreach, shelter or housing programs while homeless, per the state's definition. Lower is better, but a longer average can also mean more people are being held in programs.", fmt: (v) => `${Math.round(v)} days` },
  returns: { label: "Returned to homelessness within 6 months", note: "Of people who exited to permanent housing, the share who returned to homelessness within six months. Lower is better.", fmt: (v) => `${(v * 100).toFixed(1)}%` },
};

let state = normalizeHomelessState(data, parseHomelessHash(location.hash));

function fillTable(id, lines) {
  $(id).querySelector("tbody").replaceChildren(...lines.map((cells) => {
    const tr = document.createElement("tr");
    for (const cell of cells) { const td = document.createElement("td"); td.textContent = cell; tr.append(td); }
    return tr;
  }));
}

// Inline styles on purpose, like the peers page: the legend must survive an older cached stylesheet.
function legend(id, items) {
  const swatch = (color, style = "") => `<span style="display:inline-block;width:1.1rem;height:.8rem;margin-right:.35rem;vertical-align:-1px;background:${color};${style}"></span>`;
  $(id).style.cssText = "display:flex;flex-wrap:wrap;gap:.25rem 1rem;padding:0;list-style:none;font-size:.85rem";
  $(id).innerHTML = items.map(([color, label, style]) => `<li>${swatch(color, style)}${label}</li>`).join("");
}

const money = (v) => v === null ? "n/a" : formatMoney(v);
const perPerson = (v) => v === null ? "n/a" : formatPerResident(v);

function drawCity(rows) {
  const width = Math.max(300, $("city-chart").clientWidth);
  const bars = rows.flatMap((r) => [{ fy: String(r.fy), what: "Spending", value: r.expenditures, kind: r.kind }, { fy: String(r.fy), what: "Department revenue", value: r.revenue, kind: r.kind }]);
  $("city-chart").replaceChildren(Plot.plot({
    width, height: 280, marginLeft: 56,
    fx: { label: null, domain: rows.map((r) => String(r.fy)), tickFormat: (v) => `FY${v}` },
    x: { axis: null, domain: ["Spending", "Department revenue"] },
    y: { label: null, grid: true, tickFormat: (v) => formatMoney(v) },
    marks: [
      Plot.barY(bars, { fx: "fy", x: "what", y: "value", fill: (d) => d.what === "Spending" ? css("--accent") : css("--muted"),
        fillOpacity: (d) => d.kind === "actual" ? 1 : 0.55, title: (d) => `FY${d.fy} ${d.what.toLowerCase()} (${d.kind}): ${formatMoney(d.value)}` }),
      Plot.ruleY([0]),
    ],
  }));
  legend("city-legend", [[css("--accent"), "Spending"], [css("--muted"), "Department revenue"], [css("--text"), "Paler bars are the budget and adopted amounts, not actual spending", "opacity:.4"]]);
}

function drawHhap(rows) {
  const ids = state.regions.filter((id) => ROLE[id] === "home" || ROLE[id] === "ca");
  const bars = rows.filter((r) => ids.includes(r.coc_id) && r.perCounted !== null);
  const rounds = [...new Set(rows.map((r) => r.round))];
  $("hhap-chart").replaceChildren(Plot.plot({
    width: Math.max(300, $("hhap-chart").clientWidth), height: 280, marginLeft: 56,
    fx: { label: null, domain: rounds }, x: { axis: null, domain: ids },
    y: { label: null, grid: true, tickFormat: (v) => formatPerResident(v) },
    marks: [
      Plot.barY(bars, { fx: "round", x: "coc_id", y: "perCounted", fill: (d) => colorOf(d.coc_id),
        title: (d) => `${NAMES[d.coc_id]}, ${d.round}: ${formatPerResident(d.perCounted)} awarded per person counted` }),
      Plot.ruleY([0]),
    ],
  }));
  legend("hhap-legend", ids.map((id) => [colorOf(id), NAMES[id]]));
}

function drawLines(chartId, legendId, series, valueKey, fmt, yLabel, pointFilter = () => true) {
  const width = Math.max(300, $(chartId).clientWidth);
  const ids = state.regions;
  $(chartId).replaceChildren(Plot.plot({
    width, height: 300, marginLeft: 56, marginRight: 24,
    x: { label: null, type: "linear", tickFormat: (v) => String(v), ticks: 6 },
    y: { label: yLabel, grid: true, tickFormat: fmt },
    marks: [
      ...ids.map((id) => Plot.line(series.filter((p) => p.coc_id === id), { x: "year", y: valueKey, stroke: colorOf(id), strokeWidth: ROLE[id] === "home" ? 3 : 2, strokeDasharray: ROLE[id] === "reference" ? "5,4" : null, defined: (d) => d[valueKey] !== null })),
      Plot.dot(series.filter((p) => p[valueKey] !== null), { x: "year", y: valueKey, stroke: (d) => colorOf(d.coc_id), fill: (d) => d.carried ? css("--bg") : colorOf(d.coc_id), strokeWidth: 2, r: 4,
        title: (d) => `${NAMES[d.coc_id]}, ${d.year}: ${fmt(d[valueKey])}${d.carried ? " (unsheltered count reused)" : ""}` }),
    ],
  }));
  const shown = ids.filter((id) => series.some((p) => p.coc_id === id && p[valueKey] !== null));
  legend(legendId, shown.map((id) => [colorOf(id), NAMES[id] + (ROLE[id] === "reference" ? " (reference)" : ""), ROLE[id] === "reference" ? "opacity:.6" : ""]));
}

function headline() {
  const rows = cityPerCounted(data).filter((r) => r.kind === "actual" && r.perCounted !== null);
  if (!rows.length) { $("hhead").textContent = "The city's homelessness spending could not be matched to a count."; return; }
  const latest = rows[rows.length - 1];
  const first = rows.find((r) => r.fy === 2022) ?? rows[0];
  const n = (v) => v.toLocaleString("en-US");
  $("hhead").textContent = `In fiscal year ${latest.fy} the City of San Diego's homelessness department spent ${formatMoney(latest.expenditures)}, about ${formatPerResident(latest.perCounted)} for each of the ${n(latest.count)} people counted across the city and county on one night in January ${latest.fy}. Because the count covers the whole county, this understates the city's spending per person counted in the city. For comparison, the county count was ${n(first.count)} in January ${first.fy}.`;
}

function render() {
  headline();
  const city = cityPerCounted(data);
  drawCity(city);
  fillTable("city-table", city.map((r) => [`FY${r.fy}`, r.kind === "actual" ? "Actual" : r.kind === "budget" ? "Budget" : "Adopted", money(r.expenditures), money(r.revenue), r.count === null ? "n/a" : r.count.toLocaleString("en-US"), perPerson(r.perCounted)]));
  const hhap = hhapPerCounted(data);
  drawHhap(hhap);
  fillTable("hhap-table", hhap.filter((r) => state.regions.includes(r.coc_id)).map((r) => [r.round, NAMES[r.coc_id], money(r.awarded), String(r.pit_year), r.count === null ? "n/a" : r.count.toLocaleString("en-US"), perPerson(r.perCounted)]));
  for (const r of data.regions.filter((r) => r.role !== "home")) $(`region-${r.coc_id}`).checked = state.regions.includes(r.coc_id);
  $("measure").value = state.measure;
  const pit = pitIndex(data, state.regions);
  drawLines("pit-chart", "pit-legend", pit, "index", (v) => String(Math.round(v)), "People counted, 2019 = 100");
  fillTable("pit-table", pit.map((p) => [String(p.year), NAMES[p.coc_id], p.total === null ? "n/a" : p.total.toLocaleString("en-US"), p.index === null ? "n/a" : String(Math.round(p.index)), p.total === null ? (p.year === 2021 ? "Count waived" : "Not available") : p.carried ? "Reused unsheltered count" : ""]));
  const text = MEASURE_TEXT[state.measure];
  const out = outcomeSeries(data, state.regions, state.measure);
  $("outcome-note").textContent = text.note;
  $("outcome-col").textContent = text.label;
  $("outcome-caption").textContent = `${text.label}, reported by the state for each region and calendar year. California regions only: the state does not publish these for other states.`;
  drawLines("outcome-chart", "outcome-legend", out, "value", text.fmt, text.label);
  fillTable("outcome-table", out.map((p) => [String(p.year), NAMES[p.coc_id], text.fmt(p.value)]));
}

function buildBoxes() {
  const box = $("region-boxes");
  const parts = [["state", "California"], ["ca", "California regions"], ["peer", "US cities"], ["reference", "Reference areas"]];
  for (const [role, title] of parts) {
    for (const r of data.regions.filter((x) => x.role === role)) {
      const label = document.createElement("label");
      const input = document.createElement("input");
      input.type = "checkbox"; input.id = `region-${r.coc_id}`; input.value = r.coc_id;
      label.append(input, ` ${r.name}`);
      label.title = title;
      box.append(label);
    }
  }
}

function update() {
  const regions = data.regions.filter((r) => r.role !== "home" && $(`region-${r.coc_id}`).checked).map((r) => r.coc_id);
  state = normalizeHomelessState(data, { regions, measure: $("measure").value });
  const defaults = normalizeHomelessState(data, { regions: null, measure: "exit" }).regions;
  const isDefault = state.regions.join() === defaults.join();
  history.replaceState(null, "", serializeHomelessHash({ regions: isDefault ? null : state.regions.slice(1), measure: state.measure }) || location.pathname + location.search);
  render();
}

buildBoxes();
for (const id of ["measure", ...data.regions.filter((r) => r.role !== "home").map((r) => `region-${r.coc_id}`)]) $(id).addEventListener("change", update);
window.addEventListener("hashchange", () => { state = normalizeHomelessState(data, parseHomelessHash(location.hash)); render(); });
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);
let lastWidth = $("pit-chart").clientWidth;
new ResizeObserver(() => { const w = $("pit-chart").clientWidth; if (w !== lastWidth) { lastWidth = w; render(); } }).observe($("pit-chart"));
render();
enhanceTables();
