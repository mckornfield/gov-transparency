import test from "node:test";
import assert from "node:assert/strict";
import { parseSortValue, compareValues, sortedIndexes, firstDirection } from "./tables.js";

test("parses money, compact money, percent and plain numbers", () => {
  assert.equal(parseSortValue("$1,234"), 1234);
  assert.equal(parseSortValue("$4.2M"), 4.2e6);
  assert.equal(parseSortValue("$310K"), 310000);
  assert.equal(parseSortValue("$1.5B"), 1.5e9);
  assert.equal(parseSortValue("-$5"), -5);
  assert.equal(parseSortValue("12.5%"), 12.5);
  assert.equal(parseSortValue("1,381,162"), 1381162);
  assert.equal(parseSortValue("$0 (not provided by the city)"), 0);
  assert.equal(parseSortValue("under $1 to $547"), 0.5);
});

test("parses fiscal years and month-year dates so later sorts higher", () => {
  assert.equal(parseSortValue("FY2023"), 2023);
  assert.ok(parseSortValue("June 2024") > parseSortValue("December 2023"));
  assert.ok(parseSortValue("December 2023") > parseSortValue("September 2023"));
});

test("parses rank phrases, highest first", () => {
  assert.equal(parseSortValue("highest of 12"), 1);
  assert.equal(parseSortValue("4th highest of 12"), 4);
  assert.equal(parseSortValue("lowest of 12"), 12);
});

test("missing markers sort as null; text stays text", () => {
  for (const t of ["n/a", "—", "none", "", "  "]) assert.equal(parseSortValue(t), null);
  assert.equal(parseSortValue("Acme Inc"), "acme inc");
});

test("compareValues puts nulls last in both directions, numbers before text", () => {
  assert.ok(compareValues(1, 2, "asc") < 0);
  assert.ok(compareValues(1, 2, "desc") > 0);
  assert.ok(compareValues(null, 5, "asc") > 0);
  assert.ok(compareValues(null, 5, "desc") > 0);
  assert.ok(compareValues("a", "b", "asc") < 0);
  assert.ok(compareValues(5, "a", "asc") < 0);
});

test("sortedIndexes is stable and returns the new order of row indexes", () => {
  const cells = ["$5", "$9", "$5", "n/a", "$7"];
  assert.deepEqual(sortedIndexes(cells, "desc"), [1, 4, 0, 2, 3]);
  assert.deepEqual(sortedIndexes(cells, "asc"), [0, 2, 4, 1, 3]);
});

test("first click sorts numbers high-to-low and text A-to-Z", () => {
  assert.equal(firstDirection(["$5", "$9"]), "desc");
  assert.equal(firstDirection(["n/a", "Acme", "Zed"]), "asc");
  assert.equal(firstDirection([]), "asc");
});
