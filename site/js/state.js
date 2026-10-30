import { DEFAULTS } from "./model.js";

const BASES = ["actual", "adopted"];
const MODES = ["total", "perResident"];
const VIEWS = ["bars", "treemap"];

// Always returns a valid state: unknown values fall back to the default, never throw.
export function parseHash(hash, years) {
  const params = new URLSearchParams(String(hash).replace(/^#/, ""));
  const basis = BASES.includes(params.get("basis")) ? params.get("basis") : DEFAULTS.basis;
  const mode = MODES.includes(params.get("mode")) ? params.get("mode") : DEFAULTS.mode;
  const transfers = params.get("transfers") === "1";
  const view = VIEWS.includes(params.get("view")) ? params.get("view") : DEFAULTS.view;
  const expand = params.get("expand") === "1";
  const valid = years[basis] ?? [];
  const wanted = Number.parseInt(params.get("fy"), 10);
  let fy = DEFAULTS.fy;
  if (valid.includes(wanted)) fy = wanted;
  else if (!valid.includes(DEFAULTS.fy)) fy = valid.at(-1) ?? DEFAULTS.fy;
  return { fy, basis, mode, transfers, view, expand };
}

export function serializeHash({ fy, basis, mode, transfers, view, expand }) {
  return `#fy=${fy}&basis=${basis}&mode=${mode}&transfers=${transfers ? 1 : 0}&view=${view}&expand=${expand ? 1 : 0}`;
}
