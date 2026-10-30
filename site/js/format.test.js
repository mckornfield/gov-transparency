import test from "node:test";
import assert from "node:assert/strict";
import { formatMoney, formatPerResident, truncate } from "./format.js";

test("formatMoney scales and rounds", () => {
  assert.equal(formatMoney(3.98e9), "$4.0B");
  assert.equal(formatMoney(320e6), "$320M");
  assert.equal(formatMoney(12.34e6), "$12.3M");
  assert.equal(formatMoney(45600), "$46K");
  assert.equal(formatMoney(812), "$812");
  assert.equal(formatMoney(0), "$0");
  assert.equal(formatMoney(-2.5e6), "-$2.5M");
});

test("formatMoney never prints a rounded value at the wrong scale", () => {
  assert.equal(formatMoney(999_600), "$1.0M");
  assert.equal(formatMoney(99_960_000), "$100M");
  assert.equal(formatMoney(999_600_000), "$1.0B");
});

test("formatPerResident", () => {
  assert.equal(formatPerResident(1234.6), "$1,235");
  assert.equal(formatPerResident(-50), "-$50");
});

test("truncate cuts with an ellipsis and respects the limit", () => {
  assert.equal(truncate("Police", 10), "Police");
  assert.equal(truncate("Department of Information Technology", 12), "Department …");
  assert.equal(truncate("abcdef", 3), "ab…");
  assert.equal(truncate("abc", 0), "");
});
