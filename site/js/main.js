import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm";
import * as Plot from "https://cdn.jsdelivr.net/npm/@observablehq/plot@0.6.16/+esm";
import { rowsFromColumns, availableYears, totalsByYear, totalsByClass, buildHierarchy, rankGroups } from "./model.js";
import { parseHash, serializeHash } from "./state.js";
import { formatMoney, formatPerResident, truncate } from "./format.js";

const $ = (id) => document.getElementById(id);
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

const [spending, population, meta] = await Promise.all([
  fetch("data/spending.json").then((r) => r.json()),
  fetch("data/population.json").then((r) => r.json()),
  fetch("data/meta.json").then((r) => r.json()),
]);
const rows = rowsFromColumns(spending);
const years = availableYears(rows);
const popByFy = new Map(population.rows.map((p) => [p.fy, p]));
let state = parseHash(location.hash, years);

// One fixed colour per spending type, shared by both views and every year/basis.
const allClasses = [...new Set(rows.map((r) => r.account_class))].sort();
const palette = d3.schemeTableau10.concat(d3.schemeSet3).slice(0, allClasses.length);
const color = d3.scaleOrdinal(palette).domain(allClasses);

function drawLegend() {
  $("legend").replaceChildren(...allClasses.map((name) => {
    const li = document.createElement("li");
    const swatch = document.createElement("span");
    swatch.className = "swatch";
    swatch.style.background = color(name);
    li.append(swatch, name);
    return li;
  }));
}

const TOP_GROUPS = 15;

function drawBars(tree, fmt) {
  const groups = rankGroups(tree.root, { topN: TOP_GROUPS, expandAll: state.expand });
  const data = groups.flatMap((g) => g.children.map((c) => ({ group: g.name, type: c.name, value: c.value })));
  const width = Math.max(300, $("bars").clientWidth);
  const marginLeft = Math.round(Math.min(220, Math.max(100, width * 0.34)));
  const chart = Plot.plot({
    width,
    height: 26 * groups.length + 40,
    marginLeft,
    marginRight: 64,
    x: { label: null, grid: true, ticks: width < 500 ? 3 : 8, tickFormat: (v) => fmt(v) },
    // labels are cut to fit the margin; the full name is in each bar's hover title
    y: { label: null, domain: groups.map((g) => g.name), tickFormat: (n) => truncate(n, Math.floor(marginLeft / 6.6)) },
    color: { domain: allClasses, range: palette },
    marks: [
      Plot.barX(data, {
        y: "group", x: "value", fill: "type",
        title: (d) => `${d.group} › ${d.type}: ${fmt(d.value)}`,
      }),
      Plot.text(groups, { y: "name", x: "total", text: (g) => fmt(g.total), dx: 4, textAnchor: "start" }),
      Plot.ruleX([0]),
    ],
  });
  $("bars").replaceChildren(chart);
  const hasLongTail = rankGroups(tree.root, { topN: TOP_GROUPS }).length > TOP_GROUPS;
  $("expand").hidden = !hasLongTail && !state.expand;
  $("expand").textContent = state.expand ? `Show top ${TOP_GROUPS} only` : "Show all groups";
}

function update(patch) {
  state = parseHash(serializeHash({ ...state, ...patch }), years); // re-validates (e.g. year vs basis)
  history.replaceState(null, "", serializeHash(state));
  render();
}

function drawTotals(data) {
  const accent = css("--accent");
  const bar = css("--bar");
  const chart = Plot.plot({
    width: Math.max(300, $("totals-chart").clientWidth),
    height: 180,
    marginLeft: 56,
    x: { tickFormat: "d", label: null, tickSize: 0 },
    y: { label: null, grid: true, tickFormat: (v) => formatMoney(v) },
    marks: [
      Plot.barY(data, {
        x: "fy", y: "total",
        fill: (d) => (d.fy === state.fy ? accent : bar),
        title: (d) => `FY${d.fy}: ${formatMoney(d.total)}`,
      }),
      Plot.ruleY([0]),
    ],
  });
  $("totals-chart").replaceChildren(chart);
}

function drawTreemap(tree, fmt) {
  const el = $("treemap");
  const width = Math.max(300, el.clientWidth);
  const height = Math.round(Math.min(640, Math.max(360, width * 0.7)));
  const h = d3.hierarchy(tree.root).sum((d) => d.value ?? 0).sort((a, b) => b.value - a.value);
  d3.treemap().size([width, height]).paddingInner(1).paddingOuter(2)
    .paddingTop((d) => (d.depth === 1 ? 16 : 2)).round(true)(h);

  const svg = d3.create("svg")
    .attr("viewBox", `0 0 ${width} ${height}`).attr("width", width).attr("height", height)
    .attr("role", "img")
    .attr("aria-label", "Treemap of city spending by department group and type of spending");
  svg.selectAll("rect.leaf").data(h.leaves()).join("rect")
    .attr("class", "leaf")
    .attr("x", (d) => d.x0).attr("y", (d) => d.y0)
    .attr("width", (d) => d.x1 - d.x0).attr("height", (d) => d.y1 - d.y0)
    .attr("fill", (d) => color(d.data.name))
    .append("title").text((d) => `${d.parent.data.name} › ${d.data.name}: ${fmt(d.value)}`);
  svg.selectAll("text.group").data(h.descendants().filter((d) => d.depth === 1 && d.x1 - d.x0 > 50))
    .join("text").attr("class", "group")
    .attr("x", (d) => d.x0 + 3).attr("y", (d) => d.y0 + 12)
    .text((d) => truncate(d.data.name, Math.floor((d.x1 - d.x0) / 6.5)));
  el.replaceChildren(svg.node());
}

function fillTable(tableId, lines) {
  $(tableId).querySelector("tbody").replaceChildren(...lines.map((cells) => {
    const tr = document.createElement("tr");
    for (const text of cells) {
      const td = document.createElement("td");
      td.textContent = text;
      tr.append(td);
    }
    return tr;
  }));
}

function drawTable(tree, fmt) {
  const groups = tree.root.children
    .map((g) => ({ name: g.name, value: d3.sum(g.children, (c) => c.value) }))
    .sort((a, b) => b.value - a.value);
  const sum = d3.sum(groups, (g) => g.value);
  $("table-body").replaceChildren(...groups.map((g) => {
    const tr = document.createElement("tr");
    for (const text of [g.name, fmt(g.value), `${((100 * g.value) / sum).toFixed(1)}%`]) {
      const td = document.createElement("td");
      td.textContent = text;
      tr.append(td);
    }
    return tr;
  }));
}

function render() {
  const fyList = years[state.basis];
  const slider = $("fy");
  slider.min = fyList[0];
  slider.max = fyList.at(-1);
  slider.value = state.fy;
  $("fy-label").textContent = `FY${state.fy}`;
  document.querySelector(`input[name=basis][value=${state.basis}]`).checked = true;
  document.querySelector(`input[name=mode][value=${state.mode}]`).checked = true;
  $("transfers").checked = state.transfers;
  document.querySelector(`input[name=view][value=${state.view}]`).checked = true;
  $("bars").hidden = state.view !== "bars";
  $("treemap").hidden = state.view !== "treemap";
  $("expand").hidden = state.view !== "bars";

  const pop = popByFy.get(state.fy);
  const perResident = state.mode === "perResident";
  const fmt = perResident ? formatPerResident : formatMoney;
  const tree = buildHierarchy(rows, {
    fy: state.fy, basis: state.basis, includeTransfers: state.transfers,
    divisor: perResident ? pop.population : 1,
  });
  const label = state.basis === "actual" ? "actual spending" : "adopted budget";
  const estimated = pop.source === "reported" ? "" : " (population estimated)";
  const scope = state.transfers ? "including transfers between funds" : "excluding transfers between funds";
  $("headline").textContent =
    `FY${state.fy} ${label}, ${scope}: ${formatMoney(tree.rawTotal)}, or ${formatPerResident(tree.rawTotal / pop.population)} per resident${estimated}.`;
  $("totals-scope").textContent = state.transfers
    ? "Currently including transfers between city funds."
    : "Currently excluding transfers between city funds (about 13% of FY2023 spending); tick the box above to include them.";
  $("asof").textContent =
    `Data retrieved ${meta.retrieved} from the City's open-data portal. The latest actual spending the City has published is FY${meta.latest_actual_fy}; adopted budgets run through FY${meta.latest_budget_fy}.`;
  $("value-head").textContent = perResident ? "Per resident" : "Spending";
  $("omitted-note").textContent = tree.omitted.count
    ? `${tree.omitted.count} spending categories net to a credit (${formatMoney(tree.omitted.amount)}) and are left out of the picture; totals include them.`
    : "";

  const byYear = totalsByYear(rows, { basis: state.basis, includeTransfers: state.transfers });
  drawTotals(byYear);
  fillTable("totals-table", byYear.map((d) => [`FY${d.fy}`, formatMoney(d.total)]));
  const byClass = totalsByClass(rows, {
    fy: state.fy, basis: state.basis, includeTransfers: state.transfers,
    divisor: perResident ? pop.population : 1 });
  const classSum = byClass.reduce((sum, c) => sum + c.value, 0);
  $("class-value-head").textContent = perResident ? "Per resident" : "Spending";
  fillTable("class-table", byClass.map((c) => [c.name, fmt(c.value), `${((100 * c.value) / classSum).toFixed(1)}%`]));
  drawLegend();
  if (state.view === "bars") drawBars(tree, fmt);
  else drawTreemap(tree, fmt);
  drawTable(tree, fmt);
}

document.querySelectorAll("input[name=basis]").forEach((el) =>
  el.addEventListener("change", () => update({ basis: el.value })));
document.querySelectorAll("input[name=mode]").forEach((el) =>
  el.addEventListener("change", () => update({ mode: el.value })));
document.querySelectorAll("input[name=view]").forEach((el) =>
  el.addEventListener("change", () => update({ view: el.value })));
$("expand").addEventListener("click", () => update({ expand: !state.expand }));
$("transfers").addEventListener("change", (e) => update({ transfers: e.target.checked }));
$("fy").addEventListener("input", (e) => update({ fy: Number(e.target.value) }));
window.addEventListener("hashchange", () => { state = parseHash(location.hash, years); render(); });
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);

let lastWidth = $("view-area").clientWidth;
new ResizeObserver(() => {
  const width = $("view-area").clientWidth;
  if (width !== lastWidth) { lastWidth = width; render(); }
}).observe($("view-area"));

render();
