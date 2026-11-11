// Pure functions behind the school-money page. Dollars are general-fund spending as each district filed it with the state.

export function parseSchoolsHash(hash) {
  for (const part of String(hash || "").replace(/^#/, "").split("&")) {
    const [k, v = ""] = part.split("=");
    try { if (decodeURIComponent(k) === "d" && v) return { district: decodeURIComponent(v) }; } catch { /* ignore a malformed piece */ }
  }
  return { district: "all" };
}

export const serializeSchoolsHash = ({ district }) => (district && district !== "all" ? `#d=${encodeURIComponent(district)}` : "");

const sumTables = (tables) => {
  const out = {};
  for (const t of tables) for (const [k, v] of Object.entries(t)) out[k] = (out[k] || 0) + v;
  return out;
};

// One district, or every district added up when the code is "all" or unknown.
export function selectDistrict(data, code) {
  const one = data.districts.find((d) => d.code === code);
  if (one) return one;
  const fields = ["spending", "purpose", "revenue", "other_funds"];
  return { code: "all", name: `${data.county} school districts`, type: "All districts", ada: data.districts.reduce((s, d) => s + d.ada, 0),
    ...Object.fromEntries(fields.map((f) => [f, sumTables(data.districts.map((d) => d[f]))])) };
}

const total = (table) => Object.values(table).reduce((s, v) => s + v, 0);

export function tableRows(table, labels, ada) {
  const all = total(table);
  return labels.filter((label) => table[label]).map((label) => ({ label, dollars: table[label], share: table[label] / all, perStudent: ada > 0 ? table[label] / ada : null }));
}

export function groupShares(data, selected) {
  const all = total(selected.spending);
  const groups = [...new Set(data.categories.map((c) => c.group))];
  return groups.map((group) => ({ group, share: data.categories.filter((c) => c.group === group).reduce((s, c) => s + (selected.spending[c.label] || 0), 0) / all }));
}

const isPension = (label) => /pensions/i.test(label);

export function headline(data, selected) {
  const all = total(selected.spending);
  const cents = (v) => Math.round((100 * v) / all);
  const group = (name) => data.categories.filter((c) => c.group === name).reduce((s, c) => s + (selected.spending[c.label] || 0), 0);
  const teachers = selected.spending["Teacher salaries"] || 0;
  const pensions = data.categories.filter((c) => isPension(c.label)).reduce((s, c) => s + (selected.spending[c.label] || 0), 0);
  return `Of each general-fund dollar ${selected.name} spent in ${data.year_label}, about ${cents(teachers)} cents went to teacher salaries, ${cents(group("Salaries") - teachers)} cents to other staff salaries, ${cents(group("Benefits"))} cents to benefits (${cents(pensions)} of them pension contributions) and ${cents(group("Everything else"))} cents to everything else.`;
}

export function districtRows(data) {
  return data.districts.map((d) => {
    const all = total(d.spending);
    const share = (pick) => data.categories.filter(pick).reduce((s, c) => s + (d.spending[c.label] || 0), 0) / all;
    return { code: d.code, name: d.name, type: d.type, ada: d.ada, total: all, perStudent: d.ada > 0 ? all / d.ada : null,
      salaries: share((c) => c.group === "Salaries"), benefits: share((c) => c.group === "Benefits"), pensions: share((c) => isPension(c.label)) };
  });
}
