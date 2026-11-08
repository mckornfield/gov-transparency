// Pure functions behind the homelessness page. Missing counts stay null: nothing here turns a gap into 0, and
// city and state dollars are never added together (the city's grant revenue includes state money).

export const MEASURES = ["exit", "days", "returns"];
export const BASE_YEAR = 2019;

function hashParams(hash) {
  const params = new Map();
  for (const part of String(hash || "").replace(/^#/, "").split("&")) {
    const [k, v = ""] = part.split("=");
    if (!k) continue;
    try { params.set(decodeURIComponent(k), decodeURIComponent(v)); } catch { /* ignore a malformed piece */ }
  }
  return params;
}

export function parseHomelessHash(hash) {
  const params = hashParams(hash);
  const regions = (params.get("regions") || "").split(",").filter(Boolean);
  const measure = MEASURES.includes(params.get("measure")) ? params.get("measure") : "exit";
  return { regions: regions.length ? regions : null, measure };
}

export function serializeHomelessHash({ regions, measure }) {
  const parts = [];
  if (regions && regions.length) parts.push(`regions=${regions.join(",")}`);
  if (measure !== "exit") parts.push(`measure=${measure}`);
  return parts.length ? `#${parts.join("&")}` : "";
}

// San Diego is always shown; unknown ids are dropped; no valid choice means San Diego plus the California regions.
export function normalizeHomelessState(data, parsed) {
  const known = data.regions.map((r) => r.coc_id);
  const chosen = (parsed.regions || []).filter((id) => known.includes(id) && id !== data.home);
  const fallback = data.regions.filter((r) => r.role === "ca").map((r) => r.coc_id);
  const rest = chosen.length ? known.filter((id) => chosen.includes(id)) : fallback;
  return { regions: [data.home, ...rest.filter((id) => id !== data.home)], measure: MEASURES.includes(parsed.measure) ? parsed.measure : "exit" };
}

const countFor = (data, coc, year) => {
  const row = data.pit.find((p) => p.coc_id === coc && p.year === year);
  return row && row.total !== null ? row : null;
};

// Fiscal year N ends in June N, so it is set beside the January N count.
export function cityPerCounted(data) {
  return data.city.map((c) => {
    const count = countFor(data, data.home, c.fy);
    return { fy: c.fy, kind: c.kind, expenditures: c.expenditures, revenue: c.revenue,
      count: count ? count.total : null, carried: count ? count.carried : false,
      perCounted: count && c.kind === "actual" ? c.expenditures / count.total : null };
  });
}

export function hhapPerCounted(data) {
  return data.hhap.map((h) => {
    const awarded = h.coc + h.city + h.county; // three separate pots for the same area
    const count = countFor(data, h.coc_id, h.pit_year);
    return { round: h.round, coc_id: h.coc_id, pit_year: h.pit_year, awarded, count: count ? count.total : null,
      perCounted: count ? awarded / count.total : null };
  });
}

export function pitIndex(data, ids, base = BASE_YEAR) {
  const out = [];
  for (const id of ids) {
    const baseRow = countFor(data, id, base);
    for (const row of data.pit.filter((p) => p.coc_id === id && p.year >= base).sort((a, b) => a.year - b.year)) {
      out.push({ coc_id: id, year: row.year, total: row.total, carried: row.carried,
        index: row.total !== null && baseRow ? (row.total / baseRow.total) * 100 : null });
    }
  }
  return out;
}

const CALENDAR_YEAR = /^Jan (\d{4}) - Dec \1$/;

export function outcomeSeries(data, ids, measure) {
  const value = (id, metric, period) => {
    const m = data.measures.find((x) => x.coc_id === id && x.metric === metric && x.period === period);
    return m ? m.value : null;
  };
  const out = [];
  for (const id of ids) {
    const periods = [...new Set(data.measures.filter((m) => m.coc_id === id).map((m) => m.period))].filter((p) => CALENDAR_YEAR.test(p));
    for (const period of periods.sort()) {
      const year = Number(period.slice(4, 8));
      let v = null;
      if (measure === "exit") {
        const served = value(id, "M1a", period), exits = value(id, "M3", period);
        v = served && exits !== null ? exits / served : null;
      } else v = value(id, measure === "days" ? "M4" : "M5", period);
      if (v !== null) out.push({ coc_id: id, year, value: v });
    }
  }
  return out;
}
