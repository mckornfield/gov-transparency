const normalise = (text) => text.toLowerCase().replace(/\s+/g, " ").trim();

export function topVendors(vendors, fy, n = 25) {
  return vendors
    .filter((v) => v.amounts[fy] !== undefined)
    .map((v) => ({ name: v.name, ids: v.ids, amount: v.amounts[fy] }))
    .sort((a, b) => b.amount - a.amount)
    .slice(0, n);
}

export function concentration(vendors, fy, n = 10) {
  const all = topVendors(vendors, fy, Infinity);
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

export function parseVendorHash(hash, years) {
  const params = new URLSearchParams(String(hash).replace(/^#/, ""));
  const wanted = Number.parseInt(params.get("fy"), 10);
  const fy = years.includes(wanted) ? wanted : years.at(-1);
  const q = (params.get("q") ?? "").trim().slice(0, 80);
  return { fy, q };
}

export function serializeVendorHash({ fy, q }) {
  return q ? `#fy=${fy}&q=${encodeURIComponent(q)}` : `#fy=${fy}`;
}
