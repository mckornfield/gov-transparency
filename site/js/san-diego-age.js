import { formatMoney } from "./format.js";
import { SD_GROUPS, coverage, fundedText } from "./age-model.js";
import { runAgePage } from "./age-page.js";

const $ = (id) => document.getElementById(id);

function fill(id, lines) {
  $(id).querySelector("tbody").replaceChildren(...lines.map((cells) => {
    const tr = document.createElement("tr");
    for (const cell of cells) { const td = document.createElement("td"); td.textContent = cell; tr.append(td); }
    return tr;
  }));
}

runAgePage({
  dataUrl: "data/sd-age-spending.json",
  groups: SD_GROUPS,
  colors: ["#E69F00", "#0072B2", "#009E73"],
  loadError: "Sorry, the San Diego spending data could not be loaded. Please try again later.",
  programCells: (p) => [p.program, p.group, formatMoney(p.dollars), fundedText(p.funded), p.method === "published" ? "Published" : "Proxy", p.note],
  afterRender(data) {
    $("coverage").textContent = `Counted here: ${formatMoney(data.allocated)} of the ${formatMoney(data.total_outlays)} the three governments spend or budget (${Math.round(coverage(data) * 100)}%). Nearly all school spending is placed by age; most county and city spending is not.`;
    fill("government-table", data.governments.map((g) => [g.name, g.basis, formatMoney(g.total), formatMoney(g.allocated), `${Math.round((g.allocated / g.total) * 100)}%`]));
    fill("rest-table", data.not_allocated.map((row) => [row.name, row.government, formatMoney(row.dollars), row.reason]));
  },
});
