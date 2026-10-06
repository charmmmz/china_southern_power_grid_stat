const PALETTE = Object.freeze({
  ink: "#1B1A16",
  paper: "#F7F1E3",
  paperAlt: "#EEE7D7",
  muted: "#756F63",
  green: "#1E8E5A",
  yellow: "#E7B72D",
  red: "#C7433E",
  blue: "#2878B8",
  white: "#FFFFFF",
});

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[char]));
}

function finite(value) {
  if (value === null || value === undefined || value === "" || typeof value === "boolean") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function fixed(value, digits = 2) {
  const number = finite(value);
  return number === null ? "—" : number.toFixed(digits);
}

function shortDate(value) {
  const match = String(value || "").match(/^\d{4}-(\d{2})-(\d{2})$/);
  return match ? `${Number(match[1])}/${Number(match[2])}` : "—";
}

function monthLabel(value) {
  const months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];
  const match = String(value || "").match(/^(\d{4})-(\d{2})$/);
  return match && months[Number(match[2]) - 1] ? `${months[Number(match[2]) - 1]} ${match[1]}` : "";
}

function valueColor(value, low, high) {
  return value <= low ? PALETTE.green : value < high ? PALETTE.yellow : PALETTE.red;
}

function comparisonMarkup(data, showComparison) {
  const comparison = data?.month?.average_comparison || {};
  const delta = finite(comparison.delta_pct);
  const previous = finite(comparison.previous_daily_kwh);
  if (!showComparison || previous === null) return "PER REPORTED DAY";
  const month = monthLabel(data.previous_month?.period).split(" ")[0] || "LAST MONTH";
  if (delta === null) return `${escapeHtml(month)} AVG ${fixed(previous)} kWh`;
  const arrow = delta > 0 ? "↑" : delta < 0 ? "↓" : "→";
  return `${arrow} ${Math.abs(delta).toFixed(1)}% · ${escapeHtml(month)} ${fixed(previous)}`;
}

function billingMarkup(data) {
  const bill = data.previous_month || {};
  const reported = finite(bill.total_cost) !== null && Boolean(bill.billing_month);
  return `<section class="stat bill-stat">
    <span class="eyebrow">LAST MONTH BILL <b>${escapeHtml(monthLabel(bill.period))}</b></span>
    <strong>${reported ? `<small>¥</small>${fixed(bill.total_cost)}` : "—"}</strong>
    <span class="detail">${reported ? "ISSUED BILL" : "BILL NOT AVAILABLE"}${finite(bill.total_kwh) !== null ? ` · CALENDAR ${fixed(bill.total_kwh)} kWh` : ""}</span>
  </section>`;
}

function summaryMarkup(data, showComparison) {
  const latest = data.latest || {};
  const month = data.month || {};
  const previous = data.previous_month || {};
  const billReported = finite(previous.total_cost) !== null && Boolean(previous.billing_month);
  return `<div class="summary">
    <section class="stat latest-stat"><span class="eyebrow">LATEST DAY <b>${escapeHtml(shortDate(latest.date))}</b></span><strong>${fixed(latest.kwh)}<small>kWh</small></strong><span class="detail">${latest.date ? "REPORTED DAILY USAGE" : "WAITING FOR DAILY DATA"}</span></section>
    <section class="stat month-stat"><span class="eyebrow">THIS MONTH <b>${escapeHtml(monthLabel(month.period))}</b></span><strong>${fixed(month.total_kwh)}<small>kWh</small></strong><span class="detail">${Number(month.days || 0)} REPORTED DAYS</span></section>
    <section class="stat average-stat"><span class="eyebrow">DAILY AVERAGE</span><strong>${fixed(month.average_daily_kwh)}<small>kWh</small></strong><span class="detail">${comparisonMarkup(data, showComparison)}</span></section>
    <section class="stat previous-stat"><span class="eyebrow">LAST MONTH <b>${escapeHtml(monthLabel(previous.period))}</b></span><strong>${fixed(previous.total_kwh)}<small>kWh</small></strong><span class="detail bill-detail">${billReported ? `BILL ¥${fixed(previous.total_cost)}` : "BILL NOT AVAILABLE"}</span></section>
  </div>`;
}

function chartMarkup(data, width = 1000, height = 250) {
  const series = Array.isArray(data.series) ? data.series.filter(row => finite(row?.kwh) !== null && /^\d{4}-\d{2}-\d{2}$/.test(row.date)) : [];
  if (!series.length) return '<div class="chart-empty">Waiting for daily electricity data</div>';
  const values = series.map(row => Number(row.kwh));
  const spread = Math.max(1, Math.max(...values) - Math.min(...values));
  const min = Math.max(0, Math.min(...values) - spread * .16);
  const max = Math.max(...values) + spread * .16;
  const average = values.reduce((sum, value) => sum + value, 0) / values.length;
  const left = width < 400 ? 32 : 48, right = 18, top = 12, bottom = 28;
  const plotW = width - left - right, plotH = height - top - bottom;
  const day = value => Date.parse(`${value}T00:00:00Z`) / 86400000;
  const first = day(series[0].date), last = day(series.at(-1).date);
  const x = date => first === last ? left + plotW / 2 : left + (day(date) - first) / (last - first) * plotW;
  const y = value => top + (1 - (value - min) / (max - min)) * plotH;
  const low = finite(data.thresholds?.low) ?? 15, high = finite(data.thresholds?.high) ?? 25;
  const grid = [0, 0.5, 1].map(ratio => `<line x1="${left}" y1="${y(min + (max - min) * ratio)}" x2="${width - right}" y2="${y(min + (max - min) * ratio)}" class="grid"/><text x="${left - 10}" y="${y(min + (max - min) * ratio) + 5}" class="axis y">${(min + (max - min) * ratio).toFixed(0)}</text>`).join("");
  const segments = series.slice(1).map((row, index) => {
    const previous = series[index];
    // Missing dates remain gaps; they are never interpolated as zero usage.
    if (day(row.date) - day(previous.date) !== 1) return "";
    return `<line x1="${x(previous.date)}" y1="${y(previous.kwh)}" x2="${x(row.date)}" y2="${y(row.kwh)}" class="segment" style="stroke:${valueColor((Number(previous.kwh) + Number(row.kwh)) / 2, low, high)}"/>`;
  }).join("");
  const points = series.map((row, index) => `<circle cx="${x(row.date)}" cy="${y(row.kwh)}" r="${index === series.length - 1 ? 6 : 4}" class="point" style="fill:${valueColor(Number(row.kwh), low, high)}"/>`).join("");
  const every = Math.max(1, Math.ceil(series.length / 6));
  const labels = series.map((row, index) => index === 0 || index === series.length - 1 || (index % every === 0 && index < series.length - 2) ? `<text x="${x(row.date)}" y="${height - 12}" class="axis x">${escapeHtml(shortDate(row.date))}</text>` : "").join("");
  const groups = [];
  for (const row of series) {
    const group = groups.at(-1);
    if (!group || day(row.date) - day(group.at(-1).date) !== 1) groups.push([row]);
    else group.push(row);
  }
  const areas = groups.filter(group => group.length > 1).map(group => `<polygon points="${x(group[0].date)},${top + plotH} ${group.map(row => `${x(row.date)},${y(row.kwh)}`).join(" ")} ${x(group.at(-1).date)},${top + plotH}" class="area-fill"/>`).join("");
  return `<div class="chart-heading"><div><span class="chart-eyebrow">DAILY USAGE</span><strong>${series.length} DAY TREND</strong></div><span class="chart-legend"><i class="low-dot"></i>LOW <i class="mid-dot"></i>MID <i class="high-dot"></i>HIGH</span></div>
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="Daily electricity usage in kWh">${grid}${areas}<line x1="${left}" y1="${y(average)}" x2="${width - right}" y2="${y(average)}" class="average-line"/>${segments}${points}${labels}<text x="${width-right}" y="${top+10}" class="axis unit">kWh</text></svg>`;
}

function styles() {
  // Preserve the user's original module identity: warm paper, amber rules and serif figures.
  return `
    :host{display:block;width:100%;height:100%;font-family:inherit}
    *{box-sizing:border-box}
    .energy-shell{--energy-display-font:"DM Serif Display",Georgia,serif;--section-accent:#C58B18;--section-accent-ink:#86600F;--section-line:#C6B992; /* identity: original module */
      width:100%;height:100%;container-type:size;overflow:hidden;color:${PALETTE.ink};background:${PALETTE.paper};font-family:var(--font-family,system-ui)}
    header{height:42px;min-height:42px;display:flex;align-items:center;justify-content:space-between;gap:16px;padding:0 14px 0 10px;background:${PALETTE.paper};border-left:6px solid var(--section-accent);border-bottom:2px solid var(--section-line);line-height:1;font-weight:900;white-space:nowrap;overflow:hidden}
    .title{min-width:0;display:flex;align-items:center;gap:8px;overflow:hidden;text-overflow:ellipsis}
    .title i{width:28px;height:28px;flex:0 0 28px;display:grid;place-items:center;color:var(--section-accent);background:color-mix(in oklab,var(--section-accent) 14%,${PALETTE.paper});font-size:17px}
    .title b{font-size:20px;letter-spacing:.075em}.title em{color:${PALETTE.muted};font-size:15px;font-style:normal;letter-spacing:.055em}
    .meta{min-width:0;display:block;overflow:hidden;text-overflow:ellipsis;color:${PALETTE.muted};font-size:12px;font-weight:800;letter-spacing:.07em}
    .body{height:calc(100% - 42px);display:flex;flex-direction:column;min-height:0}
    .summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));height:112px;flex:0 0 auto;background:${PALETTE.paperAlt};border-bottom:1px solid var(--section-line)}
    .stat{min-width:0;display:flex;flex-direction:column;justify-content:center;gap:7px;padding:15px 20px 12px;overflow:hidden;border-right:1px solid var(--section-line)}
    .stat:last-child{border-right:0}
    .eyebrow{display:flex;justify-content:space-between;gap:8px;color:var(--section-accent-ink);font-size:13px;line-height:1;font-weight:900;letter-spacing:.09em;white-space:nowrap}
    .eyebrow b{font-size:12px;color:${PALETTE.ink};letter-spacing:.04em}
    .stat strong{font-family:var(--energy-display-font);font-size:42px;line-height:.88;font-weight:400;letter-spacing:-.025em;white-space:nowrap}
    .stat strong small{margin-left:.18em;font-family:var(--font-family,system-ui);font-size:.32em;font-weight:900;color:var(--section-accent);letter-spacing:0;vertical-align:.15em}
    .detail{font-size:12px;font-weight:800;color:${PALETTE.muted};letter-spacing:.02em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .chart{flex:1 1 auto;min-height:0;padding:16px 28px 6px;display:flex;flex-direction:column;gap:4px}
    .chart-heading{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex:0 0 auto}
    .chart-heading > div{display:flex;flex-direction:column;gap:5px}
    .chart-eyebrow{font-size:13px;line-height:1;font-weight:900;letter-spacing:.11em;color:var(--section-accent-ink)}
    .chart-heading strong{font-size:22px;line-height:1}.chart-legend{display:flex;gap:5px;align-items:center;font-size:11px;font-weight:900;letter-spacing:.06em;color:${PALETTE.muted}}
    .chart-legend i{width:.75em;height:.75em;border-radius:50%;margin-left:.45em}.low-dot{background:${PALETTE.green}}.mid-dot{background:${PALETTE.yellow}}.high-dot{background:${PALETTE.red}}
    svg{display:block;width:100%;height:100%;min-height:0;flex:1 1 auto;overflow:visible}
    .grid{stroke:var(--section-line);stroke-width:1;vector-effect:non-scaling-stroke}
    .area-fill{fill:${PALETTE.paperAlt};opacity:.72}
    .average-line{stroke:${PALETTE.ink};stroke-width:1.25;stroke-dasharray:6 7;opacity:.46;vector-effect:non-scaling-stroke}
    .axis{fill:${PALETTE.muted};font:700 12px var(--font-family,system-ui)}.axis.y{text-anchor:end}.axis.x{text-anchor:middle}.axis.unit{text-anchor:end;font-size:11px}
    .segment{stroke-width:5;stroke-linecap:round;vector-effect:non-scaling-stroke}.point{stroke:${PALETTE.paper};stroke-width:2;vector-effect:non-scaling-stroke}
    .chart-empty,.state{display:flex;align-items:center;justify-content:center;height:100%;padding:16px;text-align:center;color:${PALETTE.muted};font-size:14px}
    .overview .summary{height:144px}.overview .chart-heading strong{font-size:26px}.overview .chart{padding-top:18px}
    .fragment-summary .summary{height:100%;grid-template-columns:repeat(2,minmax(0,1fr))}.fragment-summary .stat:nth-child(-n+2){border-bottom:1px solid var(--section-line)}
    .fragment-billing .stat{height:100%;padding:14px 24px}.fragment-billing strong{font-size:clamp(28px,7cqmin,70px)}
    @container(max-width:700px){
      .meta{display:none}.title b{font-size:17px}.title em{font-size:12px}
      .summary,.overview .summary{grid-template-columns:repeat(2,minmax(0,1fr));height:190px}
      .stat{gap:6px;padding:10px 12px}.stat:nth-child(-n+2){border-bottom:1px solid var(--section-line)}
      .stat strong{font-size:clamp(24px,6cqw,38px)}.eyebrow{font-size:clamp(8px,1.65cqw,11px)}.eyebrow b{font-size:.9em}.detail{font-size:clamp(7px,1.55cqw,10px);line-height:1.2}
      .chart,.overview .chart{padding:10px 14px 5px}.chart-heading strong,.overview .chart-heading strong{font-size:17px}.chart-eyebrow{font-size:10px}.chart-legend{font-size:8px}
    }
    @container(max-width:430px){header{height:34px;min-height:34px;padding-left:6px}.title{gap:5px}.title b{font-size:14px}.title em{font-size:10px}.title i{width:22px;height:22px;flex-basis:22px;font-size:14px}.body{height:calc(100% - 34px)}.summary,.overview .summary{height:152px}.stat{padding:8px}.stat strong{font-size:25px}.detail{letter-spacing:0}.chart-legend{display:none}}
    @container(max-width:430px) and (max-height:280px){.full .chart{display:none}.full .summary{height:100%;flex:1}.stat strong{font-size:clamp(18px,7cqw,25px)}.stat strong small{font-size:.3em}.eyebrow b{display:none}.detail{font-size:7px}.eyebrow{letter-spacing:0}}
    @container(max-height:200px) and (min-width:431px){.full .chart{display:none}.full .summary,.overview .summary{height:100%;flex:1}.summary{grid-template-columns:repeat(4,minmax(0,1fr))}.stat{padding:6px 10px}.stat strong{font-size:28px}.eyebrow{font-size:10px}.eyebrow b{font-size:9px}.detail{font-size:8px;letter-spacing:0}}
    @container(max-height:360px) and (min-width:701px){.summary,.overview .summary{height:94px}.stat{padding:10px 18px;gap:6px}.stat strong{font-size:36px}.eyebrow{font-size:12px}.detail{font-size:10px}.chart,.overview .chart{padding-top:8px}.chart-heading strong,.overview .chart-heading strong{font-size:17px}.chart-eyebrow{font-size:10px}.chart-legend{font-size:9px}}
  `;
}

export default function render(shadow, ctx) {
  const data = ctx?.data || {};
  const options = ctx?.cell?.options || ctx?.options || {};
  let fragment = String((ctx?.cell ? ctx.cell.fragment : null) || ctx?.fragment || "full");
  // Legacy saved canvases become supported usage/billing fragments.
  if (fragment === "cost_trend") fragment = "trend";
  if (fragment === "ladder") fragment = "billing";
  const label = data.label === "ENERGY//COST" ? "ENERGY//USAGE" : data.label || "ENERGY//USAGE";
  const [primary, ...secondary] = String(label).split("//");
  const header = `<header><span class="title"><i class="ph-bold ph-lightning"></i><b>${escapeHtml(primary)}</b><em>/ ${escapeHtml(secondary.join(" / "))}</em></span><span class="meta">${escapeHtml(data.account_label || "HOME GRID")}${data.latest?.date ? ` · DATA THROUGH ${escapeHtml(shortDate(data.latest.date))}` : ""}</span></header>`;
  let body;
  if (data.error || data.empty) body = `<div class="state">${escapeHtml(data.error || data.message || "No electricity account found")}</div>`;
  else if (fragment === "billing") body = billingMarkup(data);
  else if (fragment === "trend") body = `<div class="chart">${chartMarkup(data)}</div>`;
  else body = `${summaryMarkup(data, options.show_comparison !== false)}${fragment === "summary" ? "" : `<div class="chart">${chartMarkup(data)}</div>`}`;
  shadow.innerHTML = `<link rel="stylesheet" href="/static/style/spectra-widgets.css"><style>${styles()}</style><div class="energy-shell ${fragment === "full" ? "full" : "fragment-" + escapeHtml(fragment)} ${options.layout === "overview" ? "overview" : ""}">${header}<div class="body">${body}</div></div>`;
  // Use the actual plot dimensions so text and points never stretch in a wide
  // short canvas or a tall preview. No asynchronous/client network work.
  const plot = shadow.querySelector?.(".chart svg");
  const chart = shadow.querySelector?.(".chart");
  if (plot && chart && plot.clientWidth > 60 && plot.clientHeight > 40) {
    chart.innerHTML = chartMarkup(data, plot.clientWidth, plot.clientHeight);
  }
}
