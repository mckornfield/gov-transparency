import test from "node:test";
import assert from "node:assert/strict";
import { parseHash, serializeHash } from "./state.js";

const years = { actual: [2011, 2012, 2023], adopted: [2011, 2023, 2026] };
const DEFAULT_STATE = { fy: 2023, basis: "actual", mode: "total", transfers: false, view: "bars", expand: false };

test("parses a valid hash", () => {
  assert.deepEqual(parseHash("#fy=2012&basis=actual&mode=perResident&transfers=1&view=treemap&expand=1", years),
    { fy: 2012, basis: "actual", mode: "perResident", transfers: true, view: "treemap", expand: true });
});

test("garbage falls back to defaults without throwing", () => {
  assert.deepEqual(parseHash("#fy=abc&basis=zzz&mode=%00&transfers=maybe&view=pie&expand=yes", years), DEFAULT_STATE);
  assert.deepEqual(parseHash("", years), DEFAULT_STATE);
});

test("links made before the view toggle existed open on the bar view", () => {
  assert.equal(parseHash("#fy=2015&basis=actual&mode=total&transfers=0", years).view, "bars");
});

test("a year that does not exist for the basis falls back to the default year", () => {
  assert.equal(parseHash("#fy=2030&basis=adopted", years).fy, 2023);
  assert.equal(parseHash("#fy=2026&basis=actual", years).fy, 2023);
});

test("when the default year is unavailable, the latest year is used", () => {
  assert.equal(parseHash("", { actual: [2011, 2012], adopted: [] }).fy, 2012);
});

test("serialize then parse round-trips", () => {
  const state = { fy: 2026, basis: "adopted", mode: "perResident", transfers: true, view: "treemap", expand: true };
  assert.deepEqual(parseHash(serializeHash(state), years), state);
});
