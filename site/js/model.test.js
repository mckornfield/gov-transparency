import test from "node:test";
import assert from "node:assert/strict";
import { rowsFromColumns, availableYears, totalsByYear, totalsByClass, buildHierarchy, rankGroups } from "./model.js";

const columns = ["basis", "fy", "dept_group", "dept_name", "account_type", "account_class", "amount"];
const rows = rowsFromColumns({ columns, rows: [
  ["actual", 2023, "Police", "Police", "Personnel", "Personnel Cost", 600],
  ["actual", 2023, "Police", "Police", "Non-Personnel", "Supplies", 100],
  ["actual", 2023, "Police", "Police", "Non-Personnel", "Transfers Out", 50],
  ["actual", 2023, "Library", "Library", "Non-Personnel", "Supplies", -30],
  ["actual", 2022, "Police", "Police", "Personnel", "Personnel Cost", 900],
  ["adopted", 2023, "Police", "Police", "Personnel", "Personnel Cost", 700],
] });

test("rowsFromColumns builds objects", () => {
  assert.deepEqual(rows[0], { basis: "actual", fy: 2023, dept_group: "Police", dept_name: "Police",
    account_type: "Personnel", account_class: "Personnel Cost", amount: 600 });
});

test("availableYears per basis", () => {
  assert.deepEqual(availableYears(rows), { actual: [2022, 2023], adopted: [2023] });
});

test("totalsByYear hides transfers unless asked", () => {
  assert.deepEqual(totalsByYear(rows, { basis: "actual" }), [{ fy: 2022, total: 900 }, { fy: 2023, total: 670 }]);
  assert.equal(totalsByYear(rows, { basis: "actual", includeTransfers: true })[1].total, 720);
});

test("buildHierarchy nests group -> class, sorted, excluding transfers by default", () => {
  const { root, total, rawTotal } = buildHierarchy(rows, { fy: 2023, basis: "actual" });
  assert.deepEqual(root.children.map((g) => g.name), ["Police"]);
  assert.deepEqual(root.children[0].children, [
    { name: "Personnel Cost", value: 600 }, { name: "Supplies", value: 100 }]);
  assert.equal(total, 670);
  assert.equal(rawTotal, 670);
});

test("net-credit leaves are omitted from the tree, kept in the total, and disclosed", () => {
  const { root, total, omitted } = buildHierarchy(rows, { fy: 2023, basis: "actual" });
  assert.ok(!root.children.some((g) => g.name === "Library"));
  assert.equal(total, 670); // includes the -30
  assert.deepEqual(omitted, { amount: -30, count: 1 });
});

test("includeTransfers adds the transfers leaf", () => {
  const { root, total } = buildHierarchy(rows, { fy: 2023, basis: "actual", includeTransfers: true });
  assert.deepEqual(root.children[0].children.map((c) => c.name), ["Personnel Cost", "Supplies", "Transfers Out"]);
  assert.equal(total, 720);
});

test("divisor scales values and total but not rawTotal", () => {
  const { root, total, rawTotal } = buildHierarchy(rows, { fy: 2023, basis: "actual", divisor: 10 });
  assert.equal(root.children[0].children[0].value, 60);
  assert.equal(total, 67);
  assert.equal(rawTotal, 670);
});

test("other basis/year are ignored and an empty selection is safe", () => {
  assert.equal(buildHierarchy(rows, { fy: 2023, basis: "adopted" }).total, 700);
  const empty = buildHierarchy(rows, { fy: 1999, basis: "actual" });
  assert.deepEqual(empty.root.children, []);
  assert.equal(empty.total, 0);
});

test("totalsByClass nets credits, sorts largest first, and honours transfers and divisor", () => {
  assert.deepEqual(totalsByClass(rows, { fy: 2023, basis: "actual" }), [
    { name: "Personnel Cost", value: 600 }, { name: "Supplies", value: 70 }]);
  assert.deepEqual(totalsByClass(rows, { fy: 2023, basis: "actual", includeTransfers: true, divisor: 10 }), [
    { name: "Personnel Cost", value: 60 }, { name: "Supplies", value: 7 }, { name: "Transfers Out", value: 5 }]);
  assert.deepEqual(totalsByClass(rows, { fy: 1999, basis: "actual" }), []);
});

const makeRoot = (count) => ({ name: "root", children: Array.from({ length: count }, (_, i) => ({
  name: `G${i}`, children: [{ name: "Personnel Cost", value: 100 + i }, { name: "Supplies", value: 10 }] })) });

test("rankGroups keeps the top N by total and merges the rest into one 'All other' bar", () => {
  const ranked = rankGroups(makeRoot(20), { topN: 15 });
  assert.equal(ranked.length, 16);
  assert.deepEqual(ranked.slice(0, 3).map((g) => g.name), ["G19", "G18", "G17"]);
  const other = ranked.at(-1);
  assert.equal(other.name, "All other (5 groups)");
  // G0..G4: personnel 100+101+102+103+104 = 510, supplies 5*10 = 50
  assert.deepEqual(other.children, [{ name: "Personnel Cost", value: 510 }, { name: "Supplies", value: 50 }]);
  assert.equal(other.total, 560);
});

test("rankGroups conserves the total however groups are merged", () => {
  const sum = (groups) => groups.reduce((s, g) => s + g.total, 0);
  assert.equal(sum(rankGroups(makeRoot(20), { topN: 15 })), sum(rankGroups(makeRoot(20), { expandAll: true })));
});

test("rankGroups with expandAll or few groups shows every group and no 'All other'", () => {
  assert.equal(rankGroups(makeRoot(20), { expandAll: true }).length, 20);
  const few = rankGroups(makeRoot(4), { topN: 15 });
  assert.equal(few.length, 4);
  assert.ok(!few.some((g) => g.name.startsWith("All other")));
  assert.deepEqual(rankGroups({ name: "root", children: [] }), []);
});
