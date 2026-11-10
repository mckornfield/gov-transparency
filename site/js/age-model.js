// Pure functions behind the age page. Dollars are federal outlays the page could tie to an age; the rest is
// "not allocated" and is never spread over ages to make the picture look complete.

export const GROUPS = ["Retirement", "Health", "Veterans", "Kids and education", "Food aid", "Housing aid", "Tax credits"];
export const MEASURES = ["person", "total"];

export function parseAgeHash(hash) {
  const params = new Map();
  for (const part of String(hash || "").replace(/^#/, "").split("&")) {
    const [k, v = ""] = part.split("=");
    if (!k) continue;
    try { params.set(decodeURIComponent(k), decodeURIComponent(v)); } catch { /* ignore a malformed piece */ }
  }
  const raw = params.get("groups");
  return { measure: params.get("measure") || "person", groups: raw ? raw.split(",").filter(Boolean) : null };
}

export function serializeAgeHash({ measure, groups }) {
  const parts = [];
  if (groups) parts.push(`groups=${groups.join(",")}`);
  if (measure !== "person") parts.push(`measure=${measure}`);
  return parts.length ? `#${parts.join("&")}` : "";
}

export function normalizeAgeState(parsed) {
  const chosen = (parsed.groups || []).filter((g) => GROUPS.includes(g));
  return { measure: MEASURES.includes(parsed.measure) ? parsed.measure : "person", groups: chosen.length ? GROUPS.filter((g) => chosen.includes(g)) : GROUPS };
}

// One row per bracket and group, in dollars per person or total dollars.
export function bandValues(data, groups, measure) {
  const rows = [];
  for (const band of data.bands) {
    for (const group of groups) {
      const dollars = data.programs.filter((p) => p.group === group).reduce((sum, p) => sum + p.by_band[band.key], 0);
      rows.push({ band: band.key, group, value: measure === "person" ? dollars / band.population : dollars });
    }
  }
  return rows;
}

export function groupTotals(data) {
  const out = {};
  for (const p of data.programs) out[p.group] = (out[p.group] || 0) + p.dollars;
  return out;
}

export const coverage = (data) => data.allocated / data.total_outlays;

const perPerson = (data, band, groups) => {
  const info = data.bands.find((b) => b.key === band);
  const dollars = data.programs.filter((p) => groups.includes(p.group)).reduce((sum, p) => sum + p.by_band[band], 0);
  return dollars / info.population;
};

// The headline: the youngest and the most-served bracket, per person.
export function ratioText(data, groups) {
  const values = data.bands.map((b) => ({ key: b.key, value: perPerson(data, b.key, groups) }));
  const top = values.reduce((a, b) => (b.value > a.value ? b : a));
  const young = values[0];
  const money = (v) => `$${Math.round(v).toLocaleString("en-US")}`;
  const name = (k) => (k === "85+" ? "85 and over" : k.replace("-", "–"));
  // Only compare when the youngest bracket is a real, different recipient; a near-zero base makes a meaningless ratio.
  const ratio = top.key !== young.key && young.value >= 50 ? ` The youngest bracket (${name(young.key)}) received ${money(young.value)}, about ${(top.value / young.value).toFixed(1)} times less.` : "";
  return `Of the programs counted here, the bracket aged ${name(top.key)} received the most per person in FY${data.fiscal_year}: ${money(top.value)}.${ratio}`;
}
