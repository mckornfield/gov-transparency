import test from "node:test";
import assert from "node:assert/strict";
import { topVendors, concentration, searchVendors, parseVendorHash, serializeVendorHash, vendorAmount, summaryFor, breakdown, yearLabel } from "./vendors-model.js";

const vendors = [
  { name: "Water Authority", ids: "1", amounts: { 2024: 500, 2025: 300 } },
  { name: "Acme (West) Inc", ids: "2", amounts: { 2024: 100 } },
  { name: "Beta Construction", ids: "3", amounts: { 2025: 200 } },
  { name: "Gamma Water Works", ids: "4", amounts: { 2025: 50, 2024: 60 } },
];

test("topVendors lists only vendors paid that year, largest first", () => {
  assert.deepEqual(topVendors(vendors, 2025, 2), [
    { name: "Water Authority", ids: "1", amount: 300 }, { name: "Beta Construction", ids: "3", amount: 200 }]);
  assert.deepEqual(topVendors(vendors, 2024).map((v) => v.name), ["Water Authority", "Acme (West) Inc", "Gamma Water Works"]);
  assert.deepEqual(topVendors(vendors, 1999), []);
});

test("concentration reports the share of the listed total held by the top n", () => {
  assert.deepEqual(concentration(vendors, 2025, 1), { count: 3, total: 550, topTotal: 300, share: 300 / 550 });
  assert.deepEqual(concentration(vendors, 1999), { count: 0, total: 0, topTotal: 0, share: 0 });
});

test("searchVendors matches names literally, case-insensitively, and ranks by the selected year", () => {
  assert.deepEqual(searchVendors(vendors, "water", 2025).map((v) => v.name), ["Water Authority", "Gamma Water Works"]);
  assert.deepEqual(searchVendors(vendors, "  WATER   works ", 2025).map((v) => v.name), ["Gamma Water Works"]);
});

test("searchVendors never treats the query as a regular expression", () => {
  assert.deepEqual(searchVendors(vendors, "(west)", 2024).map((v) => v.name), ["Acme (West) Inc"]);
  // "(" is literally in "Acme (West) Inc": it matches that name and does not throw
  assert.deepEqual(searchVendors(vendors, "(", 2024).map((v) => v.name), ["Acme (West) Inc"]);
  for (const q of [".*", "\\", "[", "a**", "?"]) assert.deepEqual(searchVendors(vendors, q, 2025), []);
});

test("searchVendors returns nothing for an empty or blank query and honours the limit", () => {
  assert.deepEqual(searchVendors(vendors, "", 2025), []);
  assert.deepEqual(searchVendors(vendors, "   ", 2025), []);
  assert.equal(searchVendors(vendors, "a", 2025, 2).length, 2);
});

test("parseVendorHash validates the year and trims the query", () => {
  const years = [2022, 2023, 2024, 2025, 2026];
  assert.deepEqual(parseVendorHash("#fy=2024&q=%20water%20", years), { fy: 2024, q: "water", dept: null });
  assert.deepEqual(parseVendorHash("#fy=1999", years), { fy: 2026, q: "", dept: null });
  assert.deepEqual(parseVendorHash("#fy=abc&q=" + "x".repeat(200), years), { fy: 2026, q: "x".repeat(80), dept: null });
  assert.deepEqual(parseVendorHash("", years), { fy: 2026, q: "", dept: null });
});

test("serializeVendorHash round-trips and omits an empty query", () => {
  const years = [2022, 2023, 2024, 2025, 2026];
  assert.equal(serializeVendorHash({ fy: 2025, q: "" }), "#fy=2025");
  const state = { fy: 2025, q: "water authority & co", dept: "Parks & Recreation" };
  assert.deepEqual(parseVendorHash(serializeVendorHash(state), years, ["Parks & Recreation"]), state);
});

const withDepts = [
  { name: "Water Authority", ids: "1", amounts: { 2025: 300 }, by_dept: { 2025: [[0, 250], [1, 50]] } },
  { name: "Beta Construction", ids: "3", amounts: { 2025: 200 }, by_dept: { 2025: [[1, 200]] } },
];

test("a department filter counts only what that department paid each vendor", () => {
  assert.equal(vendorAmount(withDepts[0], 2025, 1), 50);
  assert.equal(vendorAmount(withDepts[0], 2025, 2), undefined);
  assert.equal(vendorAmount(withDepts[0], 2025), 300);
  assert.deepEqual(topVendors(withDepts, 2025, 25, 1).map((v) => [v.name, v.amount]), [["Beta Construction", 200], ["Water Authority", 50]]);
  assert.deepEqual(topVendors(withDepts, 2025, 25, 0).map((v) => v.name), ["Water Authority"]);
  assert.deepEqual(concentration(withDepts, 2025, 1, 1), { count: 2, total: 250, topTotal: 200, share: 0.8 });
});

test("an unknown department in the link is ignored and the default year can be a full year", () => {
  const years = [2022, 2026, 2027];
  assert.deepEqual(parseVendorHash("#d=Nope", years, ["Library"], 2026), { fy: 2026, q: "", dept: null });
  assert.deepEqual(parseVendorHash("#fy=2027&d=Library", years, ["Library"], 2026), { fy: 2027, q: "", dept: "Library" });
});

test("summaries, breakdowns and partial-year labels", () => {
  const data = { partial: { 2027: "July to September 2026" },
    totals: { 2026: { all: { total: 10 }, departments: { Library: { total: 4 } } } } };
  assert.equal(summaryFor(data, 2026).total, 10);
  assert.equal(summaryFor(data, 2026, "Library").total, 4);
  assert.equal(summaryFor(data, 2026, "Police"), null);
  assert.equal(summaryFor(data, 1999), null);
  assert.deepEqual(breakdown({ Supplies: 5, Contracts: 9, Other: 5 }, ["Other", "Supplies"]).map((r) => r.label), ["Contracts", "Other", "Supplies"]);
  assert.equal(yearLabel(data, 2027), "FY2027 so far (July to September 2026)");
  assert.equal(yearLabel(data, 2026), "FY2026");
});

test("department names with slashes and ampersands survive the link", () => {
  const years = [2026];
  const state = { fy: 2026, q: "", dept: "Citywide Other/Special Funds" };
  assert.deepEqual(parseVendorHash(serializeVendorHash(state), years, ["Citywide Other/Special Funds"]), state);
});
