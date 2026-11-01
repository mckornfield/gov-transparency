// Collapsible, sortable tables. The pure helpers (parse/compare) are tested in tables.test.js;
// enhanceTables() wires them to every table inside a .table-wrap and survives pages rewriting the table body.
const MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"];
const SUFFIX = { K: 1e3, M: 1e6, B: 1e9 };

export function parseSortValue(text) {
  const t = String(text ?? "").trim();
  if (t === "" || ["n/a", "—", "-", "none"].includes(t.toLowerCase())) return null;
  let m = /^FY(\d{4})$/.exec(t);
  if (m) return Number(m[1]);
  m = /^([A-Za-z]+) (\d{4})$/.exec(t);
  if (m && MONTHS.includes(m[1].toLowerCase())) return Number(m[2]) + MONTHS.indexOf(m[1].toLowerCase()) / 12;
  m = /^(?:(\d+)(?:st|nd|rd|th) )?highest of \d+$/.exec(t);
  if (m) return m[1] ? Number(m[1]) : 1;
  m = /^lowest of (\d+)$/.exec(t);
  if (m) return Number(m[1]);
  if (/^under \$1/i.test(t)) return 0.5;
  m = /^([-−])?\$(\d[\d,]*\.?\d*|\.\d+)([KMB])?/.exec(t);
  if (m) return (m[1] ? -1 : 1) * Number(m[2].replace(/,/g, "")) * (SUFFIX[m[3]] || 1);
  m = /^([-−+])?(\d[\d,]*\.?\d*|\.\d+)%?$/.exec(t);
  if (m) return ("-−".includes(m[1] ?? "+") ? -1 : 1) * Number(m[2].replace(/,/g, ""));
  return t.toLowerCase();
}

// Missing values sort last in either direction; numbers sort before text.
export function compareValues(a, b, dir) {
  if (a === null || b === null) return a === b ? 0 : a === null ? 1 : -1;
  const sign = dir === "desc" ? -1 : 1;
  const aNum = typeof a === "number", bNum = typeof b === "number";
  if (aNum && bNum) return sign * (a - b);
  if (aNum !== bNum) return aNum ? -1 : 1;
  return sign * a.localeCompare(b);
}

export function sortedIndexes(cellTexts, dir) {
  const values = cellTexts.map(parseSortValue);
  return values.map((_, i) => i).sort((i, j) => compareValues(values[i], values[j], dir) || i - j);
}

export function firstDirection(cellTexts) {
  const first = cellTexts.map(parseSortValue).find((v) => v !== null);
  return typeof first === "number" ? "desc" : "asc";
}

function titleOf(table) {
  if (table.dataset.title) return table.dataset.title;
  const caption = table.querySelector("caption")?.textContent.trim() ?? "";
  return caption.split(/(?<=\.)\s/)[0] || "Table";
}

function enhance(table) {
  const wrap = table.closest(".table-wrap");
  const details = document.createElement("details");
  details.className = "table-details";
  details.open = true;
  const summary = document.createElement("summary");
  summary.textContent = `Table: ${titleOf(table)}`;
  wrap.before(details);
  details.append(summary, wrap);
  const syncHidden = () => { details.hidden = table.hidden; };
  syncHidden();
  new MutationObserver(syncHidden).observe(table, { attributes: true, attributeFilter: ["hidden"] });

  let sort = null;
  const [defaultCol, defaultDir] = (table.dataset.defaultSort || "").split(":");
  if (defaultCol !== undefined && defaultCol !== "") sort = { col: Number(defaultCol), dir: defaultDir === "asc" ? "asc" : "desc" };

  const body = () => table.tBodies[0];
  const headers = () => [...table.querySelectorAll("thead th")];
  let busy = false;

  function apply() {
    if (!sort || !body()) return;
    if (sort.col >= headers().length) sort = null;
    busy = true;
    if (sort) {
      const rows = [...body().rows];
      const order = sortedIndexes(rows.map((r) => r.cells[sort.col]?.textContent ?? ""), sort.dir);
      body().replaceChildren(...order.map((i) => rows[i]));
    }
    headers().forEach((th, i) => th.setAttribute("aria-sort", sort && sort.col === i ? (sort.dir === "asc" ? "ascending" : "descending") : "none"));
    queueMicrotask(() => { busy = false; });
  }

  function decorate() {
    headers().forEach((th, i) => {
      if (th.querySelector("button")) return;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "sort-button";
      button.textContent = th.textContent;
      button.addEventListener("click", () => {
        const cells = [...body().rows].map((r) => r.cells[i]?.textContent ?? "");
        sort = sort && sort.col === i ? { col: i, dir: sort.dir === "asc" ? "desc" : "asc" } : { col: i, dir: firstDirection(cells) };
        apply();
      });
      th.replaceChildren(button);
    });
    apply();
  }

  decorate();
  new MutationObserver(() => { if (!busy) apply(); }).observe(body(), { childList: true });
  // subtree: pages rewrite a header's text (e.g. "Spending" / "Per resident"), which removes its sort button
  if (table.tHead) new MutationObserver(() => { if (!busy) decorate(); }).observe(table.tHead, { childList: true, subtree: true });
}

export function enhanceTables(root = document) {
  root.querySelectorAll(".table-wrap > table").forEach(enhance);
}
