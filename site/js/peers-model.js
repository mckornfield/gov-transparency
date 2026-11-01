import { formatPerResident } from "./format.js";

export const KINDS = ["core", "utility", "outside", "debt", "other"];
export const DEFAULT_KINDS = ["core"];

const decode = (text) => { try { return decodeURIComponent(text); } catch { return ""; } };

function hashParams(hash) {
  const params = new Map();
  for (const part of String(hash || "").replace(/^#/, "").split("&")) {
    const i = part.indexOf("=");
    if (i > 0) params.set(part.slice(0, i), decode(part.slice(i + 1)));
  }
  return params;
}

export function parsePeerHash(hash) {
  const params = hashParams(hash);
  const kinds = (params.get("kinds") || "").split(",").filter((k) => KINDS.includes(k));
  const year = /^\d{4}$/.test(params.get("year") || "") ? Number(params.get("year")) : null;
  const trend = /^[a-z]+$/.test(params.get("trend") || "") ? params.get("trend") : "all";
  return { kinds: kinds.length ? KINDS.filter((k) => kinds.includes(k)) : [...DEFAULT_KINDS], adjusted: params.get("adjust") === "1", year, trend };
}

export function serializePeerHash({ kinds, adjusted = false, year = null, trend = "all" }) {
  const parts = [];
  if (!(kinds.length === DEFAULT_KINDS.length && kinds.every((k, i) => k === DEFAULT_KINDS[i]))) parts.push(`kinds=${kinds.join(",")}`);
  if (adjusted) parts.push("adjust=1");
  if (year !== null) parts.push(`year=${year}`);
  if (trend !== "all") parts.push(`trend=${trend}`);
  return parts.length ? `#${parts.join("&")}` : "";
}

// One survey year in the single-year shape the rest of this module uses. Adjusting divides each city's
// per-resident figure by its metro price level (US average = 100) so cities are compared at the same prices.
export function yearView(data, fiscalYear, adjusted) {
  const snapshot = data.years.find((y) => y.fiscal_year === fiscalYear) ?? data.years[data.years.length - 1];
  const factor = new Map(snapshot.cities.map((c) => [c.city, adjusted && c.rpp > 0 ? 100 / c.rpp : 1]));
  return {
    fiscal_year: snapshot.fiscal_year, home: data.home, groups: data.groups, cities: snapshot.cities,
    rows: snapshot.rows.map((r) => ({ ...r, per_resident: r.per_resident * (factor.get(r.city) ?? 1) })),
  };
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

function cityTotals(view, keys) {
  const totals = new Map();
  for (const r of view.rows) if (keys.includes(r.group)) totals.set(r.city, (totals.get(r.city) || 0) + r.per_resident);
  const home = totals.get(view.home) || 0;
  const middle = median([...totals].filter(([c, v]) => c !== view.home && v > 0).map(([, v]) => v));
  return { home, middle, pct: middle ? (home / middle - 1) * 100 : null };
}

export function headline(data, kinds, adjusted = false) {
  const { home, middle, pct } = cityTotals(data, visibleGroups(data, kinds).map((g) => g.key));
  const scope = `on these services (including construction${adjusted ? ", adjusted to US-average prices" : ""})`;
  if (!middle) return `San Diego spends ${formatPerResident(home)} per resident ${scope}.`;
  const rounded = Math.round(Math.abs(pct));
  const compare = rounded === 0 ? "about the same as" : `${rounded}% ${pct >= 0 ? "more" : "less"} than`;
  return `San Diego spends ${formatPerResident(home)} per resident ${scope}, ${compare} the middle peer (${formatPerResident(middle)}).`;
}

// San Diego against the middle peer for every survey year, as reported and adjusted to the same price level.
// `service` is a group key, or "all" (also used when the key is not among the visible kinds).
export function trendSeries(data, kinds, service) {
  const groups = visibleGroups(data, kinds);
  const keys = service !== "all" && groups.some((g) => g.key === service) ? [service] : groups.map((g) => g.key);
  return data.years.map((y) => {
    const raw = cityTotals(yearView(data, y.fiscal_year, false), keys);
    const adj = cityTotals(yearView(data, y.fiscal_year, true), keys);
    return { fiscal_year: y.fiscal_year, home: raw.home, middle: raw.middle, pct: raw.pct,
      homeAdjusted: adj.home, middleAdjusted: adj.middle, pctAdjusted: adj.pct };
  });
}

const MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

// Census survey year N covers fiscal years that ended July 1 of N-1 through June 30 of N.
export function fiscalYearEnd(mmdd, surveyYear) {
  const month = Number(String(mmdd).slice(0, 2));
  if (!(month >= 1 && month <= 12)) return String(mmdd);
  return `${MONTH_NAMES[month - 1]} ${month >= 7 ? surveyYear - 1 : surveyYear}`;
}

// Rank 1 is the highest spender; say so, so "1 of 12" is not read as "best" or "cheapest".
export function rankLabel(rank, of) {
  if (rank === null || rank === undefined) return "n/a";
  if (rank === 1) return `highest of ${of}`;
  if (rank === of) return `lowest of ${of}`;
  const suffix = rank % 100 >= 11 && rank % 100 <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" })[rank % 10] || "th";
  return `${rank}${suffix} highest of ${of}`;
}

// One row per city (San Diego first) with that city's per-resident value for each visible service.
export function cityMatrix(data, kinds) {
  const columns = visibleGroups(data, kinds);
  const cities = [...data.cities].sort((a, b) => Number(b.is_home) - Number(a.is_home));
  const rows = cities.map((c) => ({
    city: c.city,
    values: columns.map((g) => data.rows.find((r) => r.city === c.city && r.group === g.key)?.per_resident ?? 0),
  }));
  return { columns, rows };
}
