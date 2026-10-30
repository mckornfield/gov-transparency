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
