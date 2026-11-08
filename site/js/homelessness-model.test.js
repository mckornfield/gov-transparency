import test from "node:test";
import assert from "node:assert/strict";
import { cityPerCounted, hhapPerCounted, pitIndex, outcomeSeries, parseHomelessHash, serializeHomelessHash, normalizeHomelessState } from "./homelessness-model.js";

const pit = (coc_id, year, total, carried = false) => ({ coc_id, year, total, sheltered: null, unsheltered: null, carried });
const data = {
  home: "CA-1",
  regions: [{ coc_id: "CA-1", name: "Home", role: "home" }, { coc_id: "CA-2", name: "Other", role: "ca" }, { coc_id: "TX-1", name: "Peer", role: "peer" }],
  pit: [pit("CA-1", 2019, 100), pit("CA-1", 2020, 110), pit("CA-1", 2021, null), pit("CA-1", 2022, 120), pit("CA-1", 2023, 130), pit("CA-1", 2024, 150),
        pit("CA-2", 2019, 1000), pit("CA-2", 2020, 900, true), pit("CA-2", 2021, null), pit("CA-2", 2022, 1100), pit("CA-2", 2023, 1100), pit("CA-2", 2024, 1200)],
  city: [{ fy: 2021, expenditures: 600, revenue: 500, kind: "actual" }, { fy: 2024, expenditures: 300, revenue: 100, kind: "actual" },
         { fy: 2026, expenditures: 400, revenue: 300, kind: "adopted" }],
  hhap: [{ round: "Round 4", coc_id: "CA-1", pit_year: 2022, coc: 10, city: 20, county: 30 }, { round: "Round 4", coc_id: "CA-2", pit_year: 2022, coc: 100, city: 200, county: 300 }],
  measures: [
    { coc_id: "CA-1", metric: "M1a", period: "Jan 2020 - Dec 2020", value: 1000 }, { coc_id: "CA-1", metric: "M3", period: "Jan 2020 - Dec 2020", value: 250 },
    { coc_id: "CA-1", metric: "M1a", period: "April 2025 - March 2026", value: 1000 }, { coc_id: "CA-1", metric: "M3", period: "April 2025 - March 2026", value: 500 },
    { coc_id: "CA-1", metric: "M5", period: "Jan 2020 - Dec 2020", value: 0.1 },
    { coc_id: "CA-1", metric: "M4", period: "Jan 2021 - Dec 2021", value: 111 },
  ],
};

test("city dollars per person counted use that year's count, keep revenue apart and never total with state money", () => {
  const rows = cityPerCounted(data);
  const fy24 = rows.find((r) => r.fy === 2024);
  assert.deepEqual([fy24.expenditures, fy24.revenue, fy24.count, fy24.perCounted], [300, 100, 150, 2]);
  assert.equal(rows.find((r) => r.fy === 2021).perCounted, null); // no 2021 count: no figure, not a divide by zero
  assert.equal(rows.find((r) => r.fy === 2026).count, null); // budget years have no count yet
  assert.ok(!("total" in fy24) && !("hhap" in fy24));
});

test("HHAP awards are the CoC, city and county pots added, divided by the count each round was based on", () => {
  const rows = hhapPerCounted(data);
  const home = rows.find((r) => r.coc_id === "CA-1");
  assert.deepEqual([home.awarded, home.count, home.perCounted], [60, 120, 0.5]);
  assert.equal(rows.find((r) => r.coc_id === "CA-2").perCounted, 600 / 1100);
});

test("count index is relative to 2019, leaves 2021 as a gap and keeps the carried-over flag", () => {
  const s = pitIndex(data, ["CA-1", "CA-2"]);
  const sd = s.filter((p) => p.coc_id === "CA-1");
  assert.deepEqual(sd.map((p) => p.year), [2019, 2020, 2021, 2022, 2023, 2024]);
  assert.equal(sd[0].index, 100);
  assert.equal(sd[2].index, null);
  assert.equal(sd[5].index, 150);
  assert.equal(s.find((p) => p.coc_id === "CA-2" && p.year === 2020).carried, true);
});

test("outcome series: exit rate is exits over people served, trailing-12-month column is left out", () => {
  const exit = outcomeSeries(data, ["CA-1"], "exit");
  assert.deepEqual(exit, [{ coc_id: "CA-1", year: 2020, value: 0.25 }]);
  assert.deepEqual(outcomeSeries(data, ["CA-1"], "days"), [{ coc_id: "CA-1", year: 2021, value: 111 }]);
  assert.deepEqual(outcomeSeries(data, ["CA-1"], "returns"), [{ coc_id: "CA-1", year: 2020, value: 0.1 }]);
});

test("hash round trips and garbage falls back to the default regions and measure", () => {
  const parsed = parseHomelessHash("#regions=CA-1,TX-1&measure=days");
  assert.deepEqual(parsed, { regions: ["CA-1", "TX-1"], measure: "days" });
  assert.equal(serializeHomelessHash(parsed), "#regions=CA-1,TX-1&measure=days");
  assert.equal(serializeHomelessHash({ regions: null, measure: "exit" }), "");
  const bad = normalizeHomelessState(data, parseHomelessHash("#regions=%E0%A4%A&measure=zzz"));
  assert.deepEqual(bad, { regions: ["CA-1", "CA-2"], measure: "exit" });
  assert.deepEqual(normalizeHomelessState(data, { regions: ["TX-1", "NOPE"], measure: "days" }), { regions: ["CA-1", "TX-1"], measure: "days" });
});
