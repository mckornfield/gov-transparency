import { formatPerResident } from "./format.js";

export const KINDS = ["core", "utility", "outside", "debt", "other"];
export const DEFAULT_KINDS = ["core"];

export function parsePeerHash(hash) {
  const m = /kinds=([^&]*)/.exec(hash || "");
  const kinds = m ? m[1].split(",").filter((k) => KINDS.includes(k)) : [];
  return { kinds: kinds.length ? KINDS.filter((k) => kinds.includes(k)) : [...DEFAULT_KINDS] };
}

export function serializePeerHash({ kinds }) {
  const same = kinds.length === DEFAULT_KINDS.length && kinds.every((k, i) => k === DEFAULT_KINDS[i]);
  return same ? "" : `#kinds=${kinds.join(",")}`;
}

export function visibleGroups(data, kinds) {
  return data.groups.filter((g) => kinds.includes(g.kind));
}

function median(values) {
  const v = [...values].sort((a, b) => a - b);
  if (!v.length) return null;
  const mid = Math.floor(v.length / 2);
  return v.length % 2 ? v[mid] : (v[mid - 1] + v[mid]) / 2;
}

// Cities reporting $0 for a service are left out of the median and rank: usually a county or district provides it.
export function groupStats(data, key) {
  const group = data.groups.find((g) => g.key === key);
  const regionOf = new Map(data.cities.map((c) => [c.city, c.region]));
  const values = data.rows.filter((r) => r.group === key).map((r) => ({
    city: r.city, region: regionOf.get(r.city), per_resident: r.per_resident, amount: r.amount, is_home: r.city === data.home,
  }));
  const home = values.find((v) => v.is_home);
  const nonzero = values.filter((v) => v.per_resident > 0);
  const mid = median(nonzero.filter((v) => !v.is_home).map((v) => v.per_resident));
  const homeIsZero = !home || home.per_resident <= 0;
  const ranked = [...nonzero].sort((a, b) => b.per_resident - a.per_resident);
  return {
    key, label: group.label, kind: group.kind, home, values, median: mid,
    min: nonzero.length ? Math.min(...nonzero.map((v) => v.per_resident)) : null,
    max: nonzero.length ? Math.max(...nonzero.map((v) => v.per_resident)) : null,
    rank: homeIsZero ? null : ranked.findIndex((v) => v.is_home) + 1, of: nonzero.length,
    homeIsZero, zeroCities: values.filter((v) => v.per_resident <= 0).map((v) => v.city),
    vsMedianPct: homeIsZero || !mid ? null : (home.per_resident / mid - 1) * 100,
  };
}

export function headline(data, kinds) {
  const keys = visibleGroups(data, kinds).map((g) => g.key);
  const totals = new Map();
  for (const r of data.rows) if (keys.includes(r.group)) totals.set(r.city, (totals.get(r.city) || 0) + r.per_resident);
  const home = totals.get(data.home) || 0;
  const mid = median([...totals].filter(([c, v]) => c !== data.home && v > 0).map(([, v]) => v));
  if (!mid) return `San Diego spends ${formatPerResident(home)} per resident on these services.`;
  const pct = Math.round(Math.abs(home / mid - 1) * 100);
  const dir = home >= mid ? "more" : "less";
  return `San Diego spends ${formatPerResident(home)} per resident on these services, ${pct}% ${dir} than the middle peer (${formatPerResident(mid)}).`;
}
