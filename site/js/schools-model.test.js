import test from "node:test";
import assert from "node:assert/strict";
import { parseSchoolsHash, serializeSchoolsHash, selectDistrict, tableRows, groupShares, headline, districtRows } from "./schools-model.js";

const data = {
  year_label: "2023-24", county: "San Diego County",
  categories: [{ label: "Teacher salaries", group: "Salaries" }, { label: "Teacher pensions (CalSTRS), paid by the district", group: "Benefits" },
    { label: "Staff pensions (CalPERS)", group: "Benefits" }, { label: "Health and welfare benefits", group: "Benefits" }, { label: "Books and supplies", group: "Everything else" }],
  purposes: ["Classroom instruction"], revenues: ["Local property taxes"],
  districts: [
    { code: "1", name: "Alpha Unified", type: "Unified School District", ada: 100,
      spending: { "Teacher salaries": 600, "Teacher pensions (CalSTRS), paid by the district": 100, "Health and welfare benefits": 100, "Books and supplies": 200 },
      purpose: { "Classroom instruction": 1000 }, revenue: { "Local property taxes": 900 }, other_funds: { "Building Fund": 50 } },
    { code: "2", name: "County Office", type: "County Office of Education", ada: 0,
      spending: { "Teacher salaries": 400, "Staff pensions (CalPERS)": 100, "Books and supplies": 500 },
      purpose: { "Classroom instruction": 1000 }, revenue: { "Local property taxes": 100 }, other_funds: {} },
  ],
};

test("hash keeps one district and falls back to the whole county", () => {
  assert.deepEqual(parseSchoolsHash("#d=1"), { district: "1" });
  assert.deepEqual(parseSchoolsHash("#x=%E0%A4%A"), { district: "all" });
  assert.equal(serializeSchoolsHash({ district: "all" }), "");
  assert.equal(serializeSchoolsHash({ district: "1" }), "#d=1");
});

test("selecting the county adds the districts up; an unknown code falls back to the county", () => {
  const all = selectDistrict(data, "all");
  assert.equal(all.name, "San Diego County school districts");
  assert.equal(all.ada, 100);
  assert.equal(all.spending["Teacher salaries"], 1000);
  assert.equal(all.other_funds["Building Fund"], 50);
  assert.equal(selectDistrict(data, "nope").name, all.name);
  // per-student figures for the county leave out agencies with no student count
  assert.equal(all.withStudents.spending["Teacher salaries"], 600);
  assert.equal(selectDistrict(data, "1").withStudents.spending["Teacher salaries"], 600);
  assert.equal(selectDistrict(data, "1").name, "Alpha Unified");
});

test("table rows give dollars, share and dollars per student, and no per-student figure without students", () => {
  const rows = tableRows(selectDistrict(data, "1").spending, data.categories.map((c) => c.label), 100);
  assert.deepEqual(rows[0], { label: "Teacher salaries", dollars: 600, share: 0.6, perStudent: 6 });
  assert.equal(rows.length, 4); // categories with no spending are left out
  assert.equal(tableRows(selectDistrict(data, "2").spending, ["Teacher salaries"], 0)[0].perStudent, null);
  const all = selectDistrict(data, "all");
  const county = tableRows(all.spending, ["Teacher salaries"], all.ada, all.withStudents.spending)[0];
  assert.deepEqual(county, { label: "Teacher salaries", dollars: 1000, share: 0.5, perStudent: 6 });
});

test("group shares add up to one", () => {
  const g = groupShares(data, selectDistrict(data, "1"));
  assert.deepEqual(g, [{ group: "Salaries", share: 0.6 }, { group: "Benefits", share: 0.2 }, { group: "Everything else", share: 0.2 }]);
});

test("headline gives cents per dollar for teachers, benefits and pensions, in neutral words", () => {
  const text = headline(data, selectDistrict(data, "1"));
  assert.match(text, /Of each general-fund dollar Alpha Unified spent in 2023-24, about 60 cents went to teacher salaries/);
  assert.match(text, /20 cents to benefits \(10 of them pension contributions\)/);
  assert.doesNotMatch(text, /waste|effective|deserve/);
});

test("district rows carry per-student spending and shares, with no per-student figure for the county office", () => {
  const rows = districtRows(data);
  assert.deepEqual(rows[0], { code: "1", name: "Alpha Unified", type: "Unified School District", ada: 100, total: 1000, perStudent: 10, salaries: 0.6, benefits: 0.2, pensions: 0.1 });
  assert.equal(rows[1].perStudent, null);
  assert.equal(rows[1].pensions, 0.1);
});
