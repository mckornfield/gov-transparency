// Compact money formatting. Thresholds sit just below each power of ten so a value that rounds up
// (999,600 -> "1.0") is printed at the next scale instead of as "$1000K".
export function formatMoney(value) {
  const sign = value < 0 ? "-" : "";
  const abs = Math.abs(value);
  if (abs >= 999.5e6) return `${sign}$${(abs / 1e9).toFixed(1)}B`;
  if (abs >= 99.95e6) return `${sign}$${Math.round(abs / 1e6)}M`;
  if (abs >= 999.5e3) return `${sign}$${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 999.5) return `${sign}$${Math.round(abs / 1e3)}K`;
  return `${sign}$${Math.round(abs)}`;
}

export function formatPerResident(value) {
  if (value !== 0 && Math.abs(value) < 0.5) return "under $1"; // never show a real amount as "$0"
  const sign = value < 0 ? "-" : "";
  return `${sign}$${Math.round(Math.abs(value)).toLocaleString("en-US")}`;
}

export function truncate(text, maxChars) {
  if (maxChars < 1) return "";
  return text.length <= maxChars ? text : `${text.slice(0, maxChars - 1)}…`;
}
