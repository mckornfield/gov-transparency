import * as Plot from "https://cdn.jsdelivr.net/npm/@observablehq/plot@0.6.16/+esm";
import { enhanceTables } from "./tables.js";
import { formatMoney, truncate } from "./format.js";
import { topVendors, concentration, searchVendors, parseVendorHash, serializeVendorHash, summaryFor, breakdown, yearLabel } from "./vendors-model.js";

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

const latestFull = data.full_years.at(-1);
const readHash = () => parseVendorHash(location.hash, data.years, data.departments, latestFull);
let state = readHash();
let selected = null; // vendor whose details are shown

$("fy").min = data.years[0];
$("fy").max = data.years.at(-1);
$("dept").append(...data.departments.map((d) => new Option(d, d)));
$("search-head").append(...data.years.map((y) => {
  const th = document.createElement("th");
  th.scope = "col";
  th.textContent = data.partial[y] ? `FY${y} (to Sept.)` : `FY${y}`;
  return th;
}), Object.assign(document.createElement("th"), { scope: "col", innerHTML: '<span class="visually-hidden">Details</span>' }));

function update(patch) {
  state = parseVendorHash(serializeVendorHash({ ...state, ...patch }), data.years, data.departments, latestFull);
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

function barsX(target, rows, label) {
  const width = Math.max(300, $(target).clientWidth);
  const marginLeft = Math.round(Math.min(240, Math.max(110, width * 0.34)));
  $(target).replaceChildren(Plot.plot({
    width, height: 24 * Math.max(rows.length, 1) + 40, marginLeft, marginRight: 64,
    x: { label: null, grid: true, ticks: width < 500 ? 3 : 8, tickFormat: (v) => formatMoney(v) },
    y: { label: null, domain: rows.map((r) => r[label]), tickFormat: (n) => truncate(n, Math.floor(marginLeft / 6.6)) },
    marks: [
      Plot.barX(rows, { y: label, x: "amount", fill: css("--accent"), title: (d) => `${d[label]}: ${money(d.amount)}` }),
      Plot.text(rows, { y: label, x: "amount", text: (d) => formatMoney(d.amount), dx: 4, textAnchor: "start" }),
      Plot.ruleX([0]),
    ],
  }));
}

function drawMonthly() {
  const values = state.dept === null ? data.monthly.all : data.monthly.departments[state.dept];
  const rows = data.monthly.months.map((m, i) => ({ month: new Date(`${m}-15T00:00:00`), amount: values[i] }));
  const start = new Date(`${state.fy - 1}-07-01T00:00:00`);
  const end = new Date(`${state.fy}-07-01T00:00:00`);
  const width = Math.max(300, $("monthly").clientWidth);
  $("monthly").replaceChildren(Plot.plot({
    width, height: 220, marginLeft: 56,
    x: { type: "utc", label: null, ticks: width < 500 ? 4 : 8 },
    y: { label: null, grid: true, tickFormat: (v) => formatMoney(v) },
    marks: [
      Plot.rectY([{ start, end }], { x1: "start", x2: "end", y1: 0, y2: Math.max(...values, 1), fill: css("--accent"), fillOpacity: 0.12 }),
      Plot.rectY(rows, { x1: (d) => new Date(d.month.getFullYear(), d.month.getMonth(), 2), x2: (d) => new Date(d.month.getFullYear(), d.month.getMonth() + 1, 0), y: "amount", fill: css("--accent"),
        title: (d) => `${d.month.toLocaleDateString("en-US", { month: "long", year: "numeric" })}: ${money(d.amount)}` }),
      Plot.ruleY([0]),
    ],
  }));
}

function drawDetails(vendor) {
  const points = data.years.filter((y) => vendor.amounts[y] !== undefined).map((y) => ({ fy: y, amount: vendor.amounts[y] }));
  $("trend-title").textContent = vendor.name;
  $("trend-figure").hidden = false;
  $("vendor-trend").replaceChildren(Plot.plot({
    width: Math.max(300, $("vendor-trend").clientWidth), height: 200, marginLeft: 56,
    x: { tickFormat: (y) => (data.partial[y] ? `${y}*` : `${y}`), label: null, tickSize: 0, domain: data.years },
    y: { label: null, grid: true, tickFormat: (v) => formatMoney(v) },
    marks: [Plot.barY(points, { x: "fy", y: "amount", fill: css("--accent"), title: (d) => `${yearLabel(data, d.fy)}: ${money(d.amount)}` }), Plot.ruleY([0])],
  }));
  const depts = vendor.by_dept[state.fy] ?? [];
  $("vendor-depts-caption").textContent = depts.length
    ? `Departments that paid ${vendor.name} in ${yearLabel(data, state.fy)}.`
    : `${vendor.name} was not paid $25,000 or more in ${yearLabel(data, state.fy)}.`;
  fillTable("vendor-depts", depts.map(([d, amount]) => [data.departments[d], money(amount)]));
  fillTable("vendor-types", (vendor.by_type[state.fy] ?? []).map(([t, amount]) => [data.types[t], money(amount)]));
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
    button.textContent = "Show details";
    button.addEventListener("click", () => { selected = vendor; drawDetails(vendor); });
    return [vendor.name, ...data.years.map((y) => (vendor.amounts[y] === undefined ? "—" : formatMoney(vendor.amounts[y]))), button];
  }));
  if (selected && !matches.includes(selected)) {
    selected = null;
    $("trend-figure").hidden = true;
  }
}

function render() {
  $("fy").value = state.fy;
  $("fy-label").textContent = yearLabel(data, state.fy);
  $("dept").value = state.dept ?? "";
  const deptIndex = state.dept === null ? null : data.departments.indexOf(state.dept);
  const summary = summaryFor(data, state.fy, state.dept);
  const conc = concentration(data.vendors, state.fy, 10, deptIndex);
  const who = state.dept === null ? "the City" : state.dept;
  const year = yearLabel(data, state.fy);
  if (!summary) {
    $("vhead").textContent = `${year}: ${who} made no payments in this file.`;
  } else {
    const small = summary.unnamed.count
      ? ` Another ${summary.unnamed.count.toLocaleString("en-US")} payees received ${formatMoney(summary.unnamed.amount)} in smaller amounts and are not named.`
      : "";
    const top = conc.count > 10 ? ` The 10 largest received ${Math.round((conc.topTotal / summary.total) * 100)}% of everything ${state.dept === null ? "it" : "the department"} paid.` : "";
    const named = state.dept === null
      ? `paid ${conc.count.toLocaleString("en-US")} vendors $25,000 or more, ${formatMoney(conc.total)} in total.`
      : `paid ${formatMoney(conc.total)} to ${conc.count.toLocaleString("en-US")} named vendors (those the City paid $25,000 or more that year).`;
    $("vhead").textContent = `${year}: ${who} ${named}${small}${top}`;
  }
  const cov = data.coverage[state.fy];
  const basis = cov?.reference_basis === "actual" ? "actual spending" : "adopted budget";
  $("vcoverage").textContent = cov && state.dept === null
    ? `For scale, the City's FY${state.fy} ${basis} was ${formatMoney(cov.reference_total)}, but the two figures are not directly comparable: the City's figure includes payroll, while these payments include capital, pass-through and other payments. Tax and garnishment payments, employees and petty cash are not in this file, so this is not total spending.`
    : data.partial[state.fy]
      ? `Only the first three months of FY${state.fy} are in this file. Tax and garnishment payments, employees and petty cash are not in it, so this is not total spending.`
      : "Tax and garnishment payments, employees and petty cash are not in this file, so this is not total spending.";
  const leaders = topVendors(data.vendors, state.fy, 25, deptIndex);
  barsX("leaders", leaders, "name");
  fillTable("leader-table", leaders.map((l) => [l.name, money(l.amount), summary ? `${((100 * l.amount) / summary.total).toFixed(1)}%` : "—"]));
  barsX("types", breakdown(summary?.types, data.types), "label");
  barsX("funds", breakdown(summary?.funds, data.funds), "label");
  drawMonthly();
  drawSearch();
  if (selected) drawDetails(selected);
}

$("fy").addEventListener("input", (e) => update({ fy: Number(e.target.value) }));
$("dept").addEventListener("change", (e) => update({ dept: e.target.value || null }));
$("q").addEventListener("input", (e) => update({ q: e.target.value }));
window.addEventListener("hashchange", () => { state = readHash(); render(); });
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);

let lastWidth = $("leaders").clientWidth;
new ResizeObserver(() => {
  const width = $("leaders").clientWidth;
  if (width !== lastWidth) { lastWidth = width; render(); }
}).observe($("leaders"));

render();

enhanceTables();
