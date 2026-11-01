import test from "node:test";
import assert from "node:assert/strict";
import { parsePeerHash, serializePeerHash, groupStats, visibleGroups, headline, DEFAULT_KINDS, yearView, trendSeries, normalizeState } from "./peers-model.js";

const city = (c, region = "South", home = false) => ({ city: c, state: "XX", region, population: 100, fy_end: "0630", is_home: home });
const data = {
  fiscal_year: 2024, home: "San Diego",
  groups: [{ key: "police", label: "Police", kind: "core" }, { key: "water", label: "Water", kind: "utility" }],
  cities: [city("San Diego", "West", true), city("A"), city("B"), city("C")],
  rows: [
    { city: "San Diego", group: "police", amount: 600, per_resident: 6 },
    { city: "A", group: "police", amount: 400, per_resident: 4 },
    { city: "B", group: "police", amount: 800, per_resident: 8 },
    { city: "C", group: "police", amount: 0, per_resident: 0 },
    { city: "San Diego", group: "water", amount: 0, per_resident: 0 },
    { city: "A", group: "water", amount: 100, per_resident: 1 },
    { city: "B", group: "water", amount: 0, per_resident: 0 },
    { city: "C", group: "water", amount: 0, per_resident: 0 },
  ],
};

test("hash defaults to core and drops unknown kinds", () => {
  assert.deepEqual(parsePeerHash("").kinds, DEFAULT_KINDS);
  assert.deepEqual(parsePeerHash("#kinds=utility,bogus").kinds, ["utility"]);
  assert.deepEqual(parsePeerHash("#kinds=bogus").kinds, DEFAULT_KINDS);
  assert.equal(serializePeerHash({ kinds: DEFAULT_KINDS }), "");
  assert.equal(serializePeerHash({ kinds: ["core", "utility"] }), "#kinds=core,utility");
});

test("stats exclude zero cities from median and rank, and list them", () => {
  const s = groupStats(data, "police");
  assert.equal(s.median, 6); // peers with spending: 4 and 8
  assert.equal(s.rank, 2); assert.equal(s.of, 3);
  assert.deepEqual(s.zeroCities, ["C"]);
  assert.equal(s.vsMedianPct, 0);
});

test("home zero gives null comparison, not a crash", () => {
  const s = groupStats(data, "water");
  assert.equal(s.homeIsZero, true); assert.equal(s.vsMedianPct, null); assert.equal(s.rank, null);
});

test("visibleGroups filters by kind", () => {
  assert.deepEqual(visibleGroups(data, ["core"]).map((g) => g.key), ["police"]);
  assert.deepEqual(visibleGroups(data, ["core", "utility"]).map((g) => g.key), ["police", "water"]);
});

test("headline states the comparison in plain words", () => {
  const h = headline(data, ["core"]);
  assert.match(h, /San Diego spends \$6 per resident/);
  assert.match(h, /middle peer/);
});

import { fiscalYearEnd, rankLabel, cityMatrix } from "./peers-model.js";
import { formatPerResident } from "./format.js";

test("fiscal year end names the real year: survey 2024 covers years ended Jul 2023 to Jun 2024", () => {
  assert.equal(fiscalYearEnd("0630", 2024), "June 2024");
  assert.equal(fiscalYearEnd("0930", 2024), "September 2023");
  assert.equal(fiscalYearEnd("1231", 2024), "December 2023");
  assert.equal(fiscalYearEnd("0701", 2024), "July 2023");
  assert.equal(fiscalYearEnd("zzzz", 2024), "zzzz");
});

test("rank label says which direction the rank runs", () => {
  assert.equal(rankLabel(1, 12), "highest of 12");
  assert.equal(rankLabel(2, 12), "2nd highest of 12");
  assert.equal(rankLabel(3, 12), "3rd highest of 12");
  assert.equal(rankLabel(11, 12), "11th highest of 12");
  assert.equal(rankLabel(12, 12), "lowest of 12");
  assert.equal(rankLabel(null, 12), "n/a");
});

test("cityMatrix gives every city's value for each visible service, San Diego first", () => {
  const m = cityMatrix(data, ["core", "utility"]);
  assert.deepEqual(m.columns.map((c) => c.key), ["police", "water"]);
  assert.equal(m.rows[0].city, "San Diego");
  assert.deepEqual(m.rows.find((r) => r.city === "A").values, [4, 1]);
  assert.equal(m.rows.length, 4);
});

test("a tiny non-zero amount is not shown as $0", () => {
  assert.equal(formatPerResident(0.49), "under $1");
  assert.equal(formatPerResident(0), "$0");
  assert.equal(formatPerResident(1234.4), "$1,234");
});

// Two survey years; San Diego prices are 20% above the US average, A is average, B is 20% below.
const PRICE = { "San Diego": 120, A: 100, B: 80 };
const snapshot = (fiscal_year, perResident) => ({
  fiscal_year,
  cities: Object.keys(PRICE).map((c) => ({ city: c, state: "XX", region: c === "San Diego" ? "West" : "South", population: 100, fy_end: "0630", is_home: c === "San Diego", rpp: PRICE[c] })),
  rows: Object.entries(perResident).flatMap(([c, byGroup]) => Object.entries(byGroup).map(([group, v]) => ({ city: c, group, amount: v * 100, per_resident: v }))),
});
const multi = {
  home: "San Diego",
  groups: [{ key: "police", label: "Police", kind: "core" }, { key: "fire", label: "Fire", kind: "core" }, { key: "water", label: "Water", kind: "utility" }],
  years: [
    snapshot(2023, { "San Diego": { police: 120, fire: 60, water: 5 }, A: { police: 100, fire: 50, water: 5 }, B: { police: 80, fire: 40, water: 5 } }),
    snapshot(2024, { "San Diego": { police: 144, fire: 72, water: 5 }, A: { police: 100, fire: 50, water: 5 }, B: { police: 80, fire: 40, water: 5 } }),
  ],
};

test("hash carries price adjustment, year and trend service, and drops garbage", () => {
  assert.deepEqual(parsePeerHash("#adjust=1&year=2023&trend=police"), { kinds: DEFAULT_KINDS, adjusted: true, year: 2023, trend: "police" });
  assert.deepEqual(parsePeerHash(""), { kinds: DEFAULT_KINDS, adjusted: false, year: null, trend: "all" });
  assert.deepEqual(parsePeerHash("#adjust=2&year=abc&trend=%00x y"), { kinds: DEFAULT_KINDS, adjusted: false, year: null, trend: "all" });
  assert.equal(serializePeerHash({ kinds: DEFAULT_KINDS, adjusted: false, year: null, trend: "all" }), "");
  assert.equal(serializePeerHash({ kinds: ["core", "utility"], adjusted: true, year: 2023, trend: "fire" }), "#kinds=core,utility&adjust=1&year=2023&trend=fire");
  assert.deepEqual(parsePeerHash("#kinds=core,utility&adjust=1"), { kinds: ["core", "utility"], adjusted: true, year: null, trend: "all" });
});

test("yearView picks the year, falls back to the latest, and divides by each city's price level", () => {
  assert.equal(yearView(multi, 2023, false).fiscal_year, 2023);
  assert.equal(yearView(multi, 1999, false).fiscal_year, 2024);
  assert.equal(yearView(multi, null, false).fiscal_year, 2024);
  const raw = yearView(multi, 2024, false);
  assert.equal(raw.rows.find((r) => r.city === "San Diego" && r.group === "police").per_resident, 144);
  const adj = yearView(multi, 2024, true);
  assert.equal(adj.rows.find((r) => r.city === "San Diego" && r.group === "police").per_resident, 120); // 144 / 1.2
  assert.equal(adj.rows.find((r) => r.city === "B" && r.group === "police").per_resident, 100); // 80 / 0.8
  assert.equal(adj.home, "San Diego");
  assert.equal(adj.rows.find((r) => r.city === "A" && r.group === "police").amount, 10000); // dollars are never adjusted
});

test("the price-adjusted comparison can flip the answer", () => {
  const raw = headline(yearView(multi, 2023, false), ["core"]);
  const adj = headline(yearView(multi, 2023, true), ["core"], true);
  assert.match(raw, /San Diego spends \$180 per resident/); assert.match(raw, /33% more than the middle peer \(\$135\)/);
  assert.match(adj, /\$150 per resident/); assert.match(adj, /adjusted/i); assert.match(adj, /the same as the middle peer/);
});

test("trend gives San Diego against the middle peer per year, as reported and price-adjusted", () => {
  const t = trendSeries(multi, ["core"], "all");
  assert.deepEqual(t.map((r) => r.fiscal_year), [2023, 2024]);
  assert.equal(t[0].home, 180); assert.equal(t[0].middle, 135); assert.ok(Math.abs(t[0].pct - 100 / 3) < 1e-9);
  assert.ok(Math.abs(t[0].pctAdjusted - 0) < 1e-9);
  assert.equal(t[1].home, 216); assert.ok(Math.abs(t[1].pct - 60) < 1e-9); assert.ok(Math.abs(t[1].pctAdjusted - 20) < 1e-9);
  assert.equal(t[1].homeAdjusted, 180); assert.equal(t[1].middleAdjusted, 150);
});

test("trend can follow one service, and ignores services outside the chosen kinds", () => {
  const police = trendSeries(multi, ["core"], "police");
  assert.equal(police[1].home, 144); assert.equal(police[1].middle, 90);
  assert.equal(trendSeries(multi, ["core"], "water")[0].home, 180); // water is not a visible kind: falls back to all visible
  assert.equal(trendSeries(multi, ["core", "utility"], "all")[0].home, 185);
});

test("trend has no gap for a year when nobody else reports spending", () => {
  const empty = { ...multi, years: [snapshot(2024, { "San Diego": { police: 5 }, A: { police: 0 }, B: { police: 0 } })] };
  const t = trendSeries(empty, ["core"], "police");
  assert.equal(t[0].middle, null); assert.equal(t[0].pct, null); assert.equal(t[0].pctAdjusted, null);
});

test("normalizeState falls back for anything the page cannot honour, including an empty selection", () => {
  const ok = { kinds: ["core"], adjusted: true, year: 2023, trend: "police" };
  assert.deepEqual(normalizeState(multi, ok), ok);
  assert.deepEqual(normalizeState(multi, { ...ok, kinds: [] }).kinds, DEFAULT_KINDS); // all boxes unticked
  assert.equal(normalizeState(multi, { ...ok, year: 2024 }).year, null); // the latest year is the default
  assert.equal(normalizeState(multi, { ...ok, year: 1850 }).year, null);
  assert.equal(normalizeState(multi, { ...ok, trend: "water" }).trend, "all"); // water is not an included kind
  assert.equal(normalizeState(multi, { ...ok, trend: "constructor" }).trend, "all");
});

test("a year in the middle with no data leaves a gap, not a bridge, in the trend", () => {
  const mid = { ...multi, years: [multi.years[0], snapshot(2023.5, { "San Diego": { police: 5 }, A: { police: 0 }, B: { police: 0 } }), multi.years[1]] };
  const t = trendSeries(mid, ["core"], "police");
  assert.deepEqual(t.map((r) => r.pct === null), [false, true, false]);
});

test("reference cities are shown but never count toward the middle peer, range, rank or trend", () => {
  const withRef = JSON.parse(JSON.stringify(multi));
  for (const y of withRef.years) {
    y.cities.push({ city: "Ref", state: "XX", region: "South", population: 10, fy_end: "0630", is_home: false, reference: true, rpp: 100 });
    y.rows.push({ city: "Ref", group: "police", amount: 1, per_resident: 1000 }, { city: "Ref", group: "fire", amount: 1, per_resident: 1000 });
  }
  const view = yearView(withRef, 2024, false);
  const s = groupStats(view, "police");
  assert.equal(s.median, 90); // A=100, B=80 only
  assert.equal(s.max, 144); // San Diego, not the reference city's 1000
  assert.equal(s.of, 3);
  assert.equal(s.values.find((v) => v.city === "Ref").is_reference, true); // still available to draw
  assert.equal(trendSeries(withRef, ["core"], "all")[1].middle, 135 + 0 * 1); // unchanged by the reference city
  assert.match(headline(view, ["core"]), /middle peer \(\$135\)/);
});
