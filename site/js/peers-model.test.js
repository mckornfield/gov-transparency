import test from "node:test";
import assert from "node:assert/strict";
import { parsePeerHash, serializePeerHash, groupStats, visibleGroups, headline, DEFAULT_KINDS } from "./peers-model.js";

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
