export const DEFAULTS = { fy: 2023, basis: "actual", mode: "total", transfers: false };
// Money moved between city funds; counting it makes the same dollars appear twice, so it is
// hidden unless the reader asks for it.
export const TRANSFERS_CLASS = "Transfers Out";

export function rowsFromColumns({ columns, rows }) {
  return rows.map((row) => Object.fromEntries(columns.map((column, i) => [column, row[i]])));
}

function selected(rows, includeTransfers) {
  return includeTransfers ? rows : rows.filter((r) => r.account_class !== TRANSFERS_CLASS);
}

export function availableYears(rows) {
  const years = { actual: new Set(), adopted: new Set() };
  for (const row of rows) years[row.basis]?.add(row.fy);
  const sorted = (set) => [...set].sort((a, b) => a - b);
  return { actual: sorted(years.actual), adopted: sorted(years.adopted) };
}

export function totalsByYear(rows, { basis, includeTransfers = false }) {
  const totals = new Map();
  for (const row of selected(rows, includeTransfers)) {
    if (row.basis === basis) totals.set(row.fy, (totals.get(row.fy) ?? 0) + row.amount);
  }
  return [...totals].sort((a, b) => a[0] - b[0]).map(([fy, total]) => ({ fy, total }));
}

export function totalsByClass(rows, { fy, basis, divisor = 1, includeTransfers = false }) {
  const totals = new Map();
  for (const row of selected(rows, includeTransfers)) {
    if (row.basis === basis && row.fy === fy) {
      totals.set(row.account_class, (totals.get(row.account_class) ?? 0) + row.amount);
    }
  }
  return [...totals].map(([name, total]) => ({ name, value: total / divisor }))
    .sort((a, b) => b.value - a.value);
}

export function buildHierarchy(rows, { fy, basis, divisor = 1, includeTransfers = false }) {
  const leaves = new Map();
  let rawTotal = 0;
  for (const row of selected(rows, includeTransfers)) {
    if (row.basis !== basis || row.fy !== fy) continue;
    rawTotal += row.amount;
    const key = `${row.dept_group}\u0000${row.account_class}`;
    leaves.set(key, (leaves.get(key) ?? 0) + row.amount);
  }
  const groups = new Map();
  let omittedAmount = 0;
  let omittedCount = 0;
  for (const [key, amount] of leaves) {
    if (amount <= 0) { // a treemap cannot draw a zero or negative area; disclosed to the reader
      omittedAmount += amount;
      omittedCount += 1;
      continue;
    }
    const [group, spendClass] = key.split("\u0000");
    if (!groups.has(group)) groups.set(group, []);
    groups.get(group).push({ name: spendClass, value: amount / divisor });
  }
  const children = [...groups].map(([name, kids]) => ({
    name, children: kids.sort((a, b) => b.value - a.value) }));
  return {
    root: { name: "City of San Diego", children },
    total: rawTotal / divisor,
    rawTotal,
    omitted: { amount: omittedAmount, count: omittedCount },
  };
}
