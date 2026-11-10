// The age page, shared by the federal and California versions. A page passes its data file, groups, colours and wording.
import * as Plot from "https://cdn.jsdelivr.net/npm/@observablehq/plot@0.6.16/+esm";
import { enhanceTables } from "./tables.js";
import { formatMoney, formatPerResident } from "./format.js";
import { parseAgeHash, serializeAgeHash, normalizeAgeState, bandValues, ratioText } from "./age-model.js";

const $ = (id) => document.getElementById(id);

export async function runAgePage({ dataUrl, groups: GROUPS, colors: COLORS, loadError, afterRender }) {
  let data;
  try {
    const response = await fetch(dataUrl);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    data = await response.json();
  } catch (error) {
    $("ahead").textContent = loadError;
    throw error;
  }

  let state = normalizeAgeState(parseAgeHash(location.hash), GROUPS);
  const label = (key) => key === "85+" ? "85 and over" : key.replace("-", "–");

  function fillTable(id, lines) {
    $(id).querySelector("tbody").replaceChildren(...lines.map((cells) => {
      const tr = document.createElement("tr");
      for (const cell of cells) { const td = document.createElement("td"); td.textContent = cell; tr.append(td); }
      return tr;
    }));
  }

  function readControls() {
    return normalizeAgeState({ measure: $("measure").value, groups: GROUPS.filter((g) => $(`g-${GROUPS.indexOf(g)}`).checked) }, GROUPS);
  }

  function update() {
    state = readControls();
    history.replaceState(null, "", serializeAgeHash(state) || location.pathname + location.search);
    render();
  }

  function drawChart() {
    const width = Math.max(300, $("age-chart").clientWidth);
    const rows = bandValues(data, state.groups, state.measure).map((r) => ({ ...r, band: label(r.band) }));
    const fmt = state.measure === "person" ? formatPerResident : formatMoney;
    $("age-chart").replaceChildren(Plot.plot({
      width, height: 340, marginLeft: 64, marginRight: 20, marginBottom: 40,
      x: { label: "Age", domain: data.bands.map((b) => label(b.key)), padding: 0.25 },
      y: { label: null, grid: true, tickFormat: (v) => fmt(v), ticks: width < 500 ? 4 : 8 },
      color: { domain: GROUPS, range: COLORS },
      marks: [
        Plot.barY(rows, { x: "band", y: "value", fill: "group", title: (d) => `${d.group}, ages ${d.band}: ${fmt(d.value)}` }),
        Plot.ruleY([0]),
      ],
    }));
    const swatch = (c) => `<span class="swatch" style="display:inline-block;width:.8rem;height:.8rem;margin-right:.3rem;vertical-align:-1px;background:${c}"></span>`;
    $("age-legend").style.cssText = "display:flex;flex-wrap:wrap;gap:.25rem 1rem;padding:0;list-style:none;font-size:.85rem";
    $("age-legend").innerHTML = GROUPS.filter((g) => state.groups.includes(g)).map((g) => `<li>${swatch(COLORS[GROUPS.indexOf(g)])}${g}</li>`).join("");
  }

  function render() {
    for (const g of GROUPS) $(`g-${GROUPS.indexOf(g)}`).checked = state.groups.includes(g);
    $("measure").value = state.measure;
    const text = ratioText(data, state.groups);
    if ($("ahead").textContent !== text) $("ahead").textContent = text;
    drawChart();
    fillTable("band-table", data.bands.map((b) => {
      const dollars = data.programs.filter((p) => state.groups.includes(p.group)).reduce((s, p) => s + p.by_band[b.key], 0);
      return [label(b.key), b.population.toLocaleString("en-US"), b.generations.join(", "), formatPerResident(dollars / b.population), formatMoney(dollars)];
    }));
    fillTable("program-table", data.programs.map((p) => [p.program, p.group, formatMoney(p.dollars), p.method === "published" ? "Published" : "Proxy", p.note]));
    afterRender(data);
  }

  for (const id of [...GROUPS.map((g, i) => `g-${i}`), "measure"]) $(id).addEventListener("change", update);
  window.addEventListener("hashchange", () => { state = normalizeAgeState(parseAgeHash(location.hash), GROUPS); render(); });
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);
  let lastWidth = $("age-chart").clientWidth;
  new ResizeObserver(() => { const w = $("age-chart").clientWidth; if (w !== lastWidth) { lastWidth = w; render(); } }).observe($("age-chart"));
  render();
  enhanceTables();
}
