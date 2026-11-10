import { formatMoney } from "./format.js";
import { CA_GROUPS, coverage, personCoverage } from "./age-model.js";
import { runAgePage } from "./age-page.js";

const $ = (id) => document.getElementById(id);

runAgePage({
  dataUrl: "data/ca-age-spending.json",
  groups: CA_GROUPS,
  colors: ["#E69F00", "#0072B2", "#56B4E9", "#CC79A7", "#F0E442", "#009E73"],
  loadError: "Sorry, the California spending data could not be loaded. Please try again later.",
  afterRender(data) {
    $("coverage").textContent = `Counted here: ${formatMoney(data.allocated)} of ${formatMoney(data.total_outlays)} in state funds (${Math.round(coverage(data) * 100)}%). The other ${Math.round((1 - coverage(data)) * 100)}% is not allocated to an age. Against only the ${formatMoney(data.person_directed)} the state spends on health and human services and education, the counted share is ${Math.round(personCoverage(data) * 100)}%. Another ${formatMoney(data.federal_through)} of federal money flows through the same departments; it is counted on the federal page, not here.`;
    $("rest-table").querySelector("tbody").replaceChildren(...data.not_allocated.map((row) => {
      const tr = document.createElement("tr");
      for (const cell of [row.name, formatMoney(row.dollars), row.reason]) { const td = document.createElement("td"); td.textContent = cell; tr.append(td); }
      return tr;
    }));
  },
});
