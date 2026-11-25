// Pure functions behind the "Who gets paid" page. A vendor carries its yearly totals (`amounts`) and, per year, the
// departments that paid it (`by_dept`, [department index, dollars] pairs) and what for (`by_type`).
const normalise = (text) => text.toLowerCase().replace(/\s+/g, " ").trim();

// What one vendor received in a year, from every department or from one (an index into data.departments).
export function vendorAmount(vendor, fy, dept = null) {
  if (dept === null) return vendor.amounts[fy];
  const pair = (vendor.by_dept?.[fy] ?? []).find(([d]) => d === dept);
  return pair ? pair[1] : undefined;
}

export function topVendors(vendors, fy, n = 25, dept = null) {
  return vendors
    .map((v) => ({ name: v.name, ids: v.ids, amount: vendorAmount(v, fy, dept) }))
    .filter((v) => v.amount !== undefined)
    .sort((a, b) => b.amount - a.amount)
    .slice(0, n);
}

export function concentration(vendors, fy, n = 10, dept = null) {
  const all = topVendors(vendors, fy, Infinity, dept);
  const total = all.reduce((sum, v) => sum + v.amount, 0);
  const topTotal = all.slice(0, n).reduce((sum, v) => sum + v.amount, 0);
  return { count: all.length, total, topTotal, share: total === 0 ? 0 : topTotal / total };
}

const sumAmounts = (v) => Object.values(v.amounts).reduce((sum, a) => sum + a, 0);

// Literal substring match on purpose: the query is never turned into a regular expression.
export function searchVendors(vendors, query, fy, limit = 50) {
  const needle = normalise(query);
  if (needle === "") return [];
  return vendors
    .filter((v) => normalise(v.name).includes(needle))
    .sort((a, b) => (b.amounts[fy] ?? 0) - (a.amounts[fy] ?? 0) || sumAmounts(b) - sumAmounts(a) || a.name.localeCompare(b.name))
    .slice(0, limit);
}

// The year's totals for the whole city or one department (by name); null when that department paid nothing that year.
export function summaryFor(data, fy, deptName = null) {
  const year = data.totals[fy];
  if (!year) return null;
  return deptName === null ? year.all : year.departments[deptName] ?? null;
}

// {label: dollars} -> [{label, amount}], largest first, in the order given for ties.
export function breakdown(parts, order = []) {
  return Object.entries(parts ?? {})
    .map(([label, amount]) => ({ label, amount }))
    .sort((a, b) => b.amount - a.amount || order.indexOf(a.label) - order.indexOf(b.label));
}

export function yearLabel(data, fy) {
  const partial = data.partial?.[fy];
  return partial ? `FY${fy} so far (${partial})` : `FY${fy}`;
}

export function parseVendorHash(hash, years, departments = [], defaultYear = years.at(-1)) {
  const params = new URLSearchParams(String(hash).replace(/^#/, ""));
  const wanted = Number.parseInt(params.get("fy"), 10);
  const fy = years.includes(wanted) ? wanted : defaultYear;
  const q = (params.get("q") ?? "").trim().slice(0, 80);
  const dept = departments.includes(params.get("d")) ? params.get("d") : null;
  return { fy, q, dept };
}

export function serializeVendorHash({ fy, q, dept = null }) {
  const parts = [`fy=${fy}`];
  if (dept) parts.push(`d=${encodeURIComponent(dept)}`);
  if (q) parts.push(`q=${encodeURIComponent(q)}`);
  return `#${parts.join("&")}`;
}
