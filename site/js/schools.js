import * as Plot from "https://cdn.jsdelivr.net/npm/@observablehq/plot@0.6.16/+esm";
import { enhanceTables } from "./tables.js";
import { formatMoney, formatPerResident, truncate } from "./format.js";
import { parseSchoolsHash, serializeSchoolsHash, selectDistrict, tableRows, groupShares, headline, districtRows } from "./schools-model.js";

const $ = (id) => document.getElementById(id);
const COLORS = { Salaries: "#0072B2", Benefits: "#E69F00", "Everything else": "#8a8a8a" };

let data;
try {
  const response = await fetch("data/schools.json");
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  data = await response.json();
} catch (error) {
  $("shead").textContent = "Sorry, the school spending data could not be loaded. Please try again later.";
  throw error;
}

const percent = (v) => `${(100 * v).toFixed(1)}%`;
const perStudent = (v) => (v === null ? "n/a" : formatPerResident(v));
let state = parseSchoolsHash(location.hash);

$("district").replaceChildren(new Option(`All of ${data.county}`, "all"), ...data.districts.map((d) => new Option(d.name, d.code)));

function fillTable(id, lines) {
  $(id).querySelector("tbody").replaceChildren(...lines.map((cells) => {
    const tr = document.createElement("tr");
    for (const cell of cells) { const td = document.createElement("td"); td.textContent = cell; tr.append(td); }
    return tr;
  }));
}

function drawChart(selected) {
  const width = Math.max(300, $("school-chart").clientWidth);
  const narrow = width < 560;
  const group = Object.fromEntries(data.categories.map((c) => [c.label, c.group]));
  const short = (label) => truncate(label.replace(/ \(.*\)/, (m) => (narrow ? "" : m)), narrow ? 24 : 60);
  const rows = tableRows(selected.spending, data.categories.map((c) => c.label), selected.ada, selected.withStudents.spending).map((r) => ({ ...r, group: group[r.label], name: short(r.label) }));
  $("school-chart").replaceChildren(Plot.plot({
    width, height: 24 * rows.length + 50, marginLeft: narrow ? 160 : 400, marginRight: 48,
    x: { label: "Share of general-fund spending", tickFormat: (v) => `${Math.round(100 * v)}%`, grid: true, ticks: narrow ? 3 : 6 },
    y: { label: null, domain: rows.map((r) => r.name) },
    color: { domain: Object.keys(COLORS), range: Object.values(COLORS) },
    marks: [
      Plot.barX(rows, { y: "name", x: "share", fill: "group", title: (d) => `${d.label}: ${percent(d.share)}, ${formatMoney(d.dollars)}` }),
      Plot.text(rows, { y: "name", x: "share", text: (d) => percent(d.share), dx: 4, textAnchor: "start" }),
      Plot.ruleX([0]),
    ],
  }));
  const swatch = (c) => `<span class="swatch" style="display:inline-block;width:.8rem;height:.8rem;margin-right:.3rem;vertical-align:-1px;background:${c}"></span>`;
  $("school-legend").style.cssText = "display:flex;flex-wrap:wrap;gap:.25rem 1rem;padding:0;list-style:none;font-size:.85rem";
  $("school-legend").innerHTML = Object.entries(COLORS).map(([g, c]) => `<li>${swatch(c)}${g}</li>`).join("");
}

function render() {
  const selected = selectDistrict(data, state.district);
  $("district").value = selected.code;
  const text = headline(data, selected);
  if ($("shead").textContent !== text) $("shead").textContent = text;
  const total = Object.values(selected.spending).reduce((s, v) => s + v, 0);
  const withStudents = Object.values(selected.withStudents.spending).reduce((s, v) => s + v, 0);
  const left = selected.code === "all" ? "; the County Office of Education, which reports no students of its own, is left out of the per-student figures" : "";
  const students = selected.ada > 0 ? `, or ${formatPerResident(withStudents / selected.ada)} for each of ${Math.round(selected.ada).toLocaleString("en-US")} students (average daily attendance${left})` : "";
  $("sgroups").textContent = `${selected.name}: ${formatMoney(total)} of general-fund spending${students}. ${groupShares(data, selected).map((g) => `${g.group} ${percent(g.share)}`).join(", ")}.`;
  drawChart(selected);
  const group = Object.fromEntries(data.categories.map((c) => [c.label, c.group]));
  fillTable("category-table", tableRows(selected.spending, data.categories.map((c) => c.label), selected.ada, selected.withStudents.spending).map((r) => [r.label, group[r.label], percent(r.share), formatMoney(r.dollars), perStudent(r.perStudent)]));
  fillTable("purpose-table", tableRows(selected.purpose, data.purposes, selected.ada, selected.withStudents.purpose).map((r) => [r.label, percent(r.share), formatMoney(r.dollars), perStudent(r.perStudent)]));
  fillTable("revenue-table", tableRows(selected.revenue, data.revenues, selected.ada, selected.withStudents.revenue).map((r) => [r.label, percent(r.share), formatMoney(r.dollars), perStudent(r.perStudent)]));
  fillTable("funds-table", Object.entries(selected.other_funds).filter(([, v]) => v).map(([name, v]) => [name, formatMoney(v)]));
  fillTable("district-table", districtRows(data).map((d) => [d.name, d.type.replace(" School District", ""), Math.round(d.ada).toLocaleString("en-US"), formatMoney(d.total), perStudent(d.perStudent), percent(d.salaries), percent(d.benefits), percent(d.pensions)]));
}

$("district").addEventListener("change", () => {
  state = { district: $("district").value };
  history.replaceState(null, "", serializeSchoolsHash(state) || location.pathname + location.search);
  render();
});
window.addEventListener("hashchange", () => { state = parseSchoolsHash(location.hash); render(); });
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);
let lastWidth = $("school-chart").clientWidth;
new ResizeObserver(() => { const w = $("school-chart").clientWidth; if (w !== lastWidth) { lastWidth = w; render(); } }).observe($("school-chart"));
render();
enhanceTables();
