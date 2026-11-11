import test from "node:test";
import assert from "node:assert/strict";
import { GROUPS, CA_GROUPS, parseAgeHash, serializeAgeHash, normalizeAgeState, bandValues, groupTotals, coverage, personCoverage, ratioText } from "./age-model.js";

const data = {
  fiscal_year: 2024, total_outlays: 1000, person_directed: 800, allocated: 600,
  bands: [{ key: "0-18", population: 10, generations: ["Gen Z"] }, { key: "65-84", population: 5, generations: ["Baby Boomers"] }],
  programs: [
    { program: "A", group: "Retirement", dollars: 500, by_band: { "0-18": 0, "65-84": 500 } },
    { program: "B", group: "Kids and education", dollars: 100, by_band: { "0-18": 100, "65-84": 0 } },
  ],
};

test("hash round trip keeps the measure and the chosen groups", () => {
  const s = parseAgeHash("#measure=total&groups=Retirement,Health");
  assert.deepEqual(s, { measure: "total", groups: ["Retirement", "Health"] });
  assert.equal(serializeAgeHash(s), "#groups=Retirement,Health&measure=total");
  assert.equal(serializeAgeHash({ measure: "person", groups: null }), "");
});

test("a garbage hash falls back to per person and every group", () => {
  const s = normalizeAgeState(parseAgeHash("#measure=banana&groups=Nope,,"));
  assert.deepEqual(s, { measure: "person", groups: GROUPS });
});

test("bandValues is per person or total and only counts the chosen groups", () => {
  const person = bandValues(data, ["Retirement"], "person");
  assert.deepEqual(person.filter((r) => r.value > 0).map((r) => [r.band, r.value]), [["65-84", 100]]);
  assert.equal(bandValues(data, ["Retirement", "Kids and education"], "total").filter((r) => r.band === "0-18").reduce((a, r) => a + r.value, 0), 100);
});

test("group totals add programs and coverage is allocated over outlays", () => {
  assert.deepEqual(groupTotals(data), { Retirement: 500, "Kids and education": 100 });
  assert.equal(coverage(data), 0.6);
  assert.equal(personCoverage(data), 0.75);
});

test("ratio text compares two brackets per person and never says deserved or effective", () => {
  const text = ratioText(data, GROUPS);
  assert.match(text, /received the most per person.*\$100/);
  assert.match(text, /received/);
  assert.doesNotMatch(text, /effective|deserve/);
});

test("the headline does not compare a bracket with itself or with a near-zero base", () => {
  const onlyKids = ratioText(data, ["Kids and education"]);
  assert.doesNotMatch(onlyKids, /times/);
  assert.match(onlyKids, /aged 0–18/);
});

test("a page with its own groups keeps only those groups and labels a split fiscal year", () => {
  assert.deepEqual(normalizeAgeState(parseAgeHash("#groups=Schools,Retirement"), CA_GROUPS).groups, ["Schools"]);
  assert.deepEqual(normalizeAgeState(parseAgeHash("#groups=Retirement"), CA_GROUPS).groups, CA_GROUPS);
  assert.match(ratioText({ ...data, year_label: "2023-24" }, GROUPS), /per person in 2023-24:/);
});

test("the headline calls a runner-up within 10% close instead of naming a lone winner", () => {
  const near = { ...data, programs: [...data.programs, { program: "C", group: "Health", dollars: 95, by_band: { "0-18": 950, "65-84": 0 } }] };
  assert.match(ratioText(near, GROUPS), /aged 0–18 received the most.*aged 65–84 is close behind at \$100\./);
  assert.doesNotMatch(ratioText(data, GROUPS), /close behind/);
});
