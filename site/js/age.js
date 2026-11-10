import { formatMoney, formatPerResident } from "./format.js";
import { GROUPS, coverage, personCoverage } from "./age-model.js";
import { runAgePage } from "./age-page.js";

const $ = (id) => document.getElementById(id);

runAgePage({
  dataUrl: "data/age-spending.json",
  groups: GROUPS,
  colors: ["#E69F00", "#56B4E9", "#009E73", "#CC79A7", "#D55E00", "#0072B2", "#F0E442", "#8a8a8a"],
  loadError: "Sorry, the federal spending data could not be loaded. Please try again later.",
  afterRender(data) {
    $("coverage").textContent = `Counted here: ${formatMoney(data.allocated)} of ${formatMoney(data.total_outlays)} in federal outlays (${Math.round(coverage(data) * 100)}%). The other ${Math.round((1 - coverage(data)) * 100)}% is not allocated to an age. Defense, interest on the debt and other costs that are mostly not payments or services to people have no recipient age to give, so against only the ${formatMoney(data.person_directed)} that goes to health, retirement, income support, veterans, education and social services, the counted share is ${Math.round(personCoverage(data) * 100)}%. Tax credits (${formatMoney(data.tax_credits)} claimed, tax year 2022) are shown in the chart but are not budget outlays and are not part of that share.`;
    const c = data.own_check, k = data.kids_share;
    $("check").textContent = `The Urban Institute's Kids' Share series, as described in news coverage, (figures not yet confirmed at the source) puts federal spending at about ${formatPerResident(k.per_child)} per child and ${formatPerResident(k.per_person_65_plus)} per person aged 65 and over. This page still counts fewer programs (for example, no federal employee retirement or ACA subsidies, and the credits are counted at the parents' age rather than the child's), so its figures are lower: about ${formatPerResident(c.per_child)} per child and ${formatPerResident(c.per_person_65_plus)} per person aged 65 and over. The dollar difference between the two groups is about ${formatPerResident(c.per_person_65_plus - c.per_child)} here, against about ${formatPerResident(k.per_person_65_plus - k.per_child)} there.`;
  },
});
