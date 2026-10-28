// 电脑版与手机版共用的代码：序列定义、区间与指数化、刻度、分面图与拆解图配置、QE/QT 时期、领先滞后计算。
// 构建时由 tools/update.sh 内联到两个页面模板的 /*__COMMON__*/ 位置；依赖页面里先定义的 DATA。
// Shared by desktop and mobile pages; inlined at /*__COMMON__*/ by tools/update.sh. Requires DATA.

const SERIES = [
  { key: "gold", name: "黄金", unit: "美元/盎司", color: "var(--s-gold)", fmt: v => v.toLocaleString("en-US", { maximumFractionDigits: 0 }) },
  { key: "oil",  name: "WTI 原油", unit: "美元/桶", color: "var(--s-oil)", fmt: v => v.toFixed(2) },
  { key: "y10",  name: "10 年期美债收益率", short: "10Y 美债", unit: "%", color: "var(--s-y10)", fmt: v => v.toFixed(2) },
];
const RANGES = [["20 年", 20], ["10 年", 10], ["5 年", 5], ["3 年", 3], ["1 年", 1]];
const SCALES = [["对数", "log"], ["线性", "lin"]];

const dates = DATA.dates.map(s => new Date(s + "T00:00:00"));
const svgNS = "http://www.w3.org/2000/svg";
const $ = id => document.getElementById(id);
const el = (tag, attrs = {}, parent) => {
  const n = document.createElementNS(svgNS, tag);
  for (const k in attrs) n.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(n);
  return n;
};
const h = (tag, props = {}, parent) => {
  const n = document.createElement(tag);
  Object.assign(n, props);
  if (parent) parent.appendChild(n);
  return n;
};
const fmtDate = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const pct = r => (r >= 0 ? "+" : "") + (r * 100).toFixed(1) + "%";

// 区间起点：从最后一个采样点往回推 N 年
function sliceIdx(years) {
  const end = dates[dates.length - 1];
  const start = new Date(end); start.setFullYear(end.getFullYear() - years);
  let i0 = dates.findIndex(d => d >= start);
  return [Math.max(0, i0), dates.length - 1];
}

// 指数 = 当前值 / 区间起点值 × 100
function indexed(i0, i1) {
  return SERIES.map(s => {
    const raw = DATA[s.key];
    let base = null;
    for (let i = i0; i <= i1; i++) if (raw[i] != null && raw[i] > 0) { base = raw[i]; break; }
    const idx = [];
    for (let i = i0; i <= i1; i++) idx.push(raw[i] != null && base ? raw[i] / base * 100 : null);
    return { ...s, base, idx };
  });
}

function logTicks(lo, hi) {
  const sets = [[1], [1, 2, 5], [1, 2, 3, 5, 7], [1, 1.5, 2, 3, 4, 5, 6, 8]];
  let best = [];
  for (const m of sets) {
    const t = [];
    for (let e = Math.floor(Math.log10(lo)) - 1; e <= Math.ceil(Math.log10(hi)); e++)
      for (const k of m) { const v = k * 10 ** e; if (v >= lo && v <= hi) t.push(v); }
    if (t.length <= 9) best = t;
    if (t.length >= 5) break;
  }
  return best;
}
function linTicks(lo, hi) {
  const raw = (hi - lo) / 6, p = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map(k => k * p).find(s => s >= raw);
  const t = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) t.push(+v.toFixed(6));
  return t;
}

// ---- 美元流动性：价格层 vs 数量层 ----
const LIQ = [
  { title: "价格/预期层 · 10 年期美债收益率（%）", short: "10Y 实际利率与名义收益率（%）", zero: true, lines: [
    { key: "real", name: "10Y 实际利率（TIPS）", color: "var(--s-real)", fmt: v => v.toFixed(2) + "%" },
    { key: "y10", name: "10Y 名义收益率", color: "var(--s-y10)", fmt: v => v.toFixed(2) + "%" } ] },
  { title: "价格层 · 美元指数（广义贸易加权）", short: "美元指数（广义贸易加权）", lines: [
    { key: "dxy", name: "美元指数", color: "var(--s-real)", fmt: v => v.toFixed(1) } ] },
  { title: "数量层 · 美联储净流动性 = 总资产 − TGA − 逆回购（万亿美元）", short: "净流动性（万亿美元）", lines: [
    { key: "netliq", name: "净流动性", color: "var(--s-real)", fmt: v => v.toFixed(2) + " 万亿" },
    { key: "walcl", name: "美联储总资产", color: "var(--text-muted)", dash: "4 3", fmt: v => v.toFixed(2) + " 万亿" } ] },
];
// 相对区间起点的变化；sign = -1 用于"减项"，使各项相加等于合计
const delta = (key, sign = 1) => (i, i0) => DATA[key][i] == null || DATA[key][i0] == null ? null : sign * (DATA[key][i] - DATA[key][i0]);
const signed = (v, d) => (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(d);
const DECOMP = [
  { title: "实际利率 = 名义 − 通胀预期（较区间起点的变化，百分点）", short: "实际利率变化拆解（百分点）", zero: true, lines: [
    { f: delta("real"), name: "Δ 实际利率", color: "var(--s-real)", w: 2.5, fmt: v => signed(v, 2) },
    { f: delta("y10"), name: "Δ 名义收益率", color: "var(--s-y10)", fmt: v => signed(v, 2) },
    { f: delta("be", -1), name: "−Δ 通胀预期", color: "var(--s-be)", fmt: v => signed(v, 2) } ] },
  { title: "净流动性 = 总资产 − TGA − 逆回购（较区间起点的累计变化，万亿美元）", short: "净流动性变化拆解（万亿美元）", zero: true, lines: [
    { f: delta("netliq"), name: "Δ 净流动性", color: "var(--s-real)", w: 2.5, fmt: v => signed(v, 2) },
    { f: delta("walcl"), name: "Δ 总资产（美联储）", color: "var(--text-muted)", dash: "4 3", fmt: v => signed(v, 2) },
    { f: delta("tga", -1), name: "−Δ TGA（财政部）", color: "var(--s-tga)", fmt: v => signed(v, 2) },
    { f: delta("rrp", -1), name: "−Δ 逆回购（货币市场）", color: "var(--s-rrp)", fmt: v => signed(v, 2) } ] },
];
const EPISODES = [
  ["QE1", "2008-11-25", "2010-03-31"], ["QE2", "2010-11-03", "2011-06-30"], ["QE3", "2012-09-13", "2014-10-29"],
  ["QT1", "2017-10-01", "2019-07-31"], ["疫情 QE", "2020-03-15", "2022-03-09"], ["QT2", "2022-06-01", "2025-12-01"],
].map(([n, a, b]) => [n, new Date(a + "T00:00:00"), new Date(b + "T00:00:00")]);

// ---- 领先滞后：净流动性 vs 实际利率 ----
const LAG_H = 6;   // 变化窗口 6 个采样点 ≈ 90 天
const LAG_MAX = 8; // 最大错位 8 个采样点 = 120 天
function corr(a, b) {
  const n = a.length, ma = a.reduce((s, v) => s + v, 0) / n, mb = b.reduce((s, v) => s + v, 0) / n;
  let sab = 0, saa = 0, sbb = 0;
  for (let i = 0; i < n; i++) { const da = a[i] - ma, db = b[i] - mb; sab += da * db; saa += da * da; sbb += db * db; }
  return sab / Math.sqrt(saa * sbb);
}
function lagRows(i0, i1) {
  const dNL = [], dRY = [];
  for (let i = i0 + LAG_H; i <= i1; i++) { dNL.push(Math.log(DATA.netliq[i] / DATA.netliq[i - LAG_H])); dRY.push(DATA.real[i] - DATA.real[i - LAG_H]); }
  const rows = [];
  for (let k = -LAG_MAX; k <= LAG_MAX; k++) {
    // k > 0：流动性变化领先实际利率变化 k 个采样点
    const a = [], b = [];
    for (let t = 0; t < dNL.length; t++) { const u = t + k; if (u >= 0 && u < dNL.length) { a.push(dNL[t]); b.push(dRY[u]); } }
    rows.push({ k, r: corr(a, b), n: a.length });
  }
  return { rows, n: dNL.length };
}
function lagText(k) { return k === 0 ? "同期" : k < 0 ? `实际利率领先 ${-k * 15} 天` : `流动性领先 ${k * 15} 天`; }
function lagMeaning(k, r) {
  if (k === 0) return r < 0 ? "两者同期反向变动，往往是同一个冲击（政策预期、财政发债/TGA）同时推动" : "两者同期同向变动";
  if (k > 0) return r < 0 ? "流动性增加之后实际利率下行，符合「流动性 → 利率」" : "流动性增加之后实际利率反而上行（扩表常伴随风险偏好与增长预期回升）";
  return r > 0 ? "实际利率上冲之后流动性增加，符合美联储对金融条件收紧的反应（利率是前提）" : "实际利率上行之后流动性减少，即收紧先在价格上体现、数量随后兑现";
}
// 重叠窗口下的粗略 95% 门槛：约 n/LAG_H 个独立样本
const lagThreshold = n => 2 / Math.sqrt(n / LAG_H);
// 最强正、负相关的位置，以及图下方的解读文字
function lagExtremes(rows) {
  return [rows.reduce((a, b) => b.r > a.r ? b : a), rows.reduce((a, b) => b.r < a.r ? b : a)];
}
function lagReading(rows, thr) {
  const [top, bot] = lagExtremes(rows);
  if (!rows.some(r => Math.abs(r.r) >= thr)) return "所选区间内，所有错位的相关系数都没有超过粗略显著门槛，看不出稳定的先后关系。";
  return `所选区间内：最强正相关在「${lagText(top.k)}」（${top.r >= 0 ? "+" : ""}${top.r.toFixed(2)}），最强负相关在「${lagText(bot.k)}」（${bot.r.toFixed(2)}）。` +
    [top, bot].filter(r => Math.abs(r.r) >= thr).map(r => `${lagText(r.k)}：${lagMeaning(r.k, r.r)}。`).join("") +
    "颜色较淡的柱子没有超过门槛。相关只说明时间上谁先动，不等于因果。";
}

function renderTable() {
  const t = $("tbl");
  const hr = h("tr", {}, h("thead", {}, t));
  const extra = [["real", "10Y 实际利率（%）", 2], ["be", "10Y 通胀预期（%）", 2], ["dxy", "美元指数", 1], ["netliq", "净流动性（万亿美元）", 2],
    ["walcl", "美联储总资产（万亿美元）", 2], ["tga", "TGA（万亿美元）", 2], ["rrp", "逆回购（万亿美元）", 2]];
  ["日期", "黄金（美元/盎司）", "WTI 原油（美元/桶）", "10 年期美债收益率（%）", ...extra.map(e => e[1])].forEach(x => h("th", { textContent: x }, hr));
  const tb = h("tbody", {}, t);
  for (let i = dates.length - 1; i >= 0; i--) {
    const r = h("tr", {}, tb);
    h("td", { textContent: DATA.dates[i] }, r);
    SERIES.forEach(s => h("td", { textContent: DATA[s.key][i] == null ? "—" : s.fmt(DATA[s.key][i]) }, r));
    extra.forEach(([k, , f]) => h("td", { textContent: DATA[k][i] == null ? "—" : DATA[k][i].toFixed(f) }, r));
  }
}

// 页面底部的数据来源与说明（两个页面相同）
function renderNote() {
  $("note").textContent =
    "数据来源：黄金 = COMEX 黄金期货（GC=F）日收盘价，来自 Yahoo Finance；原油 = WTI 现货价（FRED: DCOILWTICO）；美债 = 10 年期美国国债固定期限收益率（FRED: DGS10）；" +
    "实际利率 = 10 年期 TIPS 收益率（FRED: DFII10）；通胀预期 = 10 年期盈亏平衡通胀率（FRED: T10YIE）；美元指数 = 广义贸易加权美元指数（FRED: DTWEXBGS）；" +
    "净流动性 = 美联储总资产（WALCL，周度）− 财政部一般账户 TGA（WTREGEN，周度）− 隔夜逆回购（RRPONTSYD）。" +
    "领先滞后图用 90 天变化（6 个采样点）计算，相邻窗口重叠，门槛按约 n/6 个独立样本粗略估计，只能作参考。" +
    "采样方法：从今天起每隔 15 天取一个日期，取该日或之前最近一个交易日的值。最新一个点黄金为盘中价。" +
    "注意：2020-04-20 WTI 曾收于 -37.63 美元，该日不在采样点上，故未出现在图中。数据已内嵌在页面中，打开不需要联网。" +
    "分析思路、结论复核与更新方法见 ";
  h("a", { href: "https://github.com/ysffor/market_analysis/blob/main/docs/ANALYSIS.md", textContent: "分析文档" }, $("note"));
  $("note").appendChild(document.createTextNode("；源代码见 "));
  h("a", { href: "https://github.com/ysffor/market_analysis", textContent: "GitHub 仓库" }, $("note"));
  $("note").appendChild(document.createTextNode("。本页仅用于学习研究，不构成投资建议。"));
}

// ======== 专题验证（与上面的美元流动性分析相互独立，不受顶部区间切换影响）========
// 验证 1：沪深300全收益跌破二级债基指数，就是底部？数据按周，自 2004-12-31 起；完整验证（日度数据）见 docs/VERIFY.md
const VERIFY_DOC = "https://github.com/ysffor/market_analysis/blob/main/docs/VERIFY.md";
const VERIFY_VERDICT = "结论（2026-10-28 更正）：大体成立，但要理解为\"接近这条线\"。按 885007 校正后，2008 年以来的大底都出现在比值约 0.9–1.1、" +
  "即两条线交汇的附近；是否真正跌破取决于 885007 早年的走势：情景 A 下 2008–2014 年几次跌破都紧挨着底部，但 2015 年以后的大底都停在线的上方。" +
  "最初发布的\"不成立\"是因为复刻的二级债基指数早年涨得太少，已更正。";
const VERIFY_BASES = [["2004-12-31", "2004-12-31"], ["2010-12-31", "2010-12-31"], ["2014-12-31", "2014-12-31"], ["2018-12-31", "2018-12-31"]];
// 二级债基口径：按 885007 锚点校正的三种情景（差距形成的年份不同）和未校正的复刻，见 docs/VERIFY.md
const VERIFY_SCENARIOS = [["情景 A", "bfA"], ["情景 B", "bfB"], ["情景 C", "bfC"], ["未校正", "bf"]];
const VERIFY_SCEN_NAME = { bfA: "按 885007 校正·情景 A", bfB: "按 885007 校正·情景 B", bfC: "按 885007 校正·情景 C", bf: "未校正的复刻" };
const VERIFY_BOTTOMS = ["2008-11-04", "2012-12-03", "2014-03-20", "2016-01-28", "2019-01-03", "2020-03-19", "2022-10-31", "2024-02-02", "2024-09-13"];
const verifyState = { base: "2004-12-31", scen: "bfA" };

// 比值 = (沪深300全收益 ÷ 基准日的值) ÷ (二级债基 ÷ 基准日的值)。
// 跌破：比值在 1 以上停留 12 周以上后第一次跌到 1 以下（实时信号日）；之后 156 周（约 3 年）内的最低点用来看"还要再跌多少"
function verifyCalc(base) {
  const V = DATA.verify, B = V[verifyState.scen], b0 = Math.max(0, V.d.findIndex(s => s >= base));
  const d = V.d.slice(b0), xs = d.map(s => new Date(s + "T00:00:00"));
  const eq = V.eq.slice(b0).map(v => v / V.eq[b0] * 1000), bf = B.slice(b0).map(v => v / B[b0] * 1000);
  const R = eq.map((v, i) => v / bf[i]);
  const crosses = [];
  let run = 0;
  for (let i = 1; i < R.length; i++) {
    if (R[i] >= 1) { run++; continue; }
    if (R[i - 1] >= 1 && run >= 12) {
      let lo = i;
      for (let j = i; j < Math.min(R.length, i + 156); j++) if (eq[j] < eq[lo]) lo = j;
      crosses.push({ i, lo, dd: eq[lo] / eq[i] - 1, weeks: lo - i });
    }
    run = 0;
  }
  return { d, xs, eq, bf, R, crosses };
}
function verifySummary(c, base) {
  const head = `以 ${base} 为基准（两者都设为 1000），二级债基用${VERIFY_SCEN_NAME[verifyState.scen]}：`;
  if (!c.crosses.length) {
    // 站稳：比值第一次在 1 以上连续停留 12 周；起点之后先低于 1 的那一段不算跌破
    let run = 0, s = -1;
    for (let i = 0; i < c.R.length && s < 0; i++) { run = c.R[i] >= 1 ? run + 1 : 0; if (run >= 12) s = i; }
    let m = s;
    for (let i = Math.max(s, 0); i < c.R.length; i++) if (c.R[i] < c.R[m]) m = i;
    const pre = s > 12 ? `起点之后比值先低于 1，${c.d[s].slice(0, 7)} 站稳 1 以上；` : "";
    return head + pre + "此后没有发生过跌破。" + (s >= 0 ? `站稳后比值最低是 ${c.R[m].toFixed(2)}（${c.d[m]}）。` : "") + `最新比值 ${c.R.at(-1).toFixed(2)}。`;
  }
  return head + `共跌破 ${c.crosses.length} 次：` + c.crosses.map(x =>
    `${c.d[x.i].slice(0, 7)}（${Math.abs(x.dd) < 0.005 ? "当周即为 3 年内最低点" : `之后 3 年内再跌 ${Math.abs(x.dd * 100).toFixed(0)}%，${x.weeks} 周后见最低点`}）`).join("；") +
    `。最新比值 ${c.R.at(-1).toFixed(2)}。页面按周数据计算，和文档里按日数据算的日期可能差几天。`;
}

// 绘制：上幅两条线（对数刻度），下幅比值（1.0 为跌破线）；▼ 为跌破点，○ 为历次大底。narrow 为手机布局
function renderVerify(narrow) {
  const c = verifyCalc(verifyState.base);
  const svg = $("v1"), ro = $("v1-ro");
  svg.textContent = "";
  const W = svg.clientWidth || 360;
  const M = { l: narrow ? 36 : 48, r: narrow ? 10 : 56 }, iw = W - M.l - M.r;
  const P1 = { t: 8, h: narrow ? 200 : 280 }, P2 = { t: (narrow ? 200 : 280) + 44, h: narrow ? 120 : 150 };
  const H = P2.t + P2.h + 24;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("height", H);
  const t0 = c.xs[0].getTime(), t1 = c.xs.at(-1).getTime();
  const X = d => M.l + (d.getTime() - t0) / (t1 - t0) * iw;
  const all = [...c.eq, ...c.bf], lo1 = Math.min(...all) / 1.06, hi1 = Math.max(...all) * 1.05;
  const Y1 = v => P1.t + (1 - (Math.log(v) - Math.log(lo1)) / (Math.log(hi1) - Math.log(lo1))) * P1.h;
  const sorted = [...c.R].sort((a, b) => a - b), p95 = sorted[Math.floor(sorted.length * 0.95)];
  const lo2 = Math.min(0.8, sorted[0] * 0.97), hi2 = Math.max(1.2, Math.min(sorted.at(-1) * 1.05, p95 * 1.2));
  const Y2 = v => P2.t + (1 - (v - lo2) / (hi2 - lo2)) * P2.h;
  const g = el("g", { class: "tick" }, svg);
  for (const v of logTicks(lo1, hi1).filter((v, i, a) => a.length <= 6 || [1, 2, 5].includes(+String(v)[0]))) {
    el("line", { x1: M.l, x2: M.l + iw, y1: Y1(v), y2: Y1(v), stroke: "var(--grid)", "stroke-width": 1 }, g);
    el("text", { x: M.l - 6, y: Y1(v) + 4, "text-anchor": "end" }, g).textContent = v >= 1000 ? v.toLocaleString("en-US") : v;
  }
  for (const v of linTicks(lo2, hi2).filter((v, i, a) => a.length <= 5 || i % 2 === 0)) {
    el("line", { x1: M.l, x2: M.l + iw, y1: Y2(v), y2: Y2(v), stroke: "var(--grid)", "stroke-width": 1 }, g);
    el("text", { x: M.l - 6, y: Y2(v) + 4, "text-anchor": "end" }, g).textContent = v.toFixed(1);
  }
  el("line", { x1: M.l, x2: M.l + iw, y1: Y2(1), y2: Y2(1), stroke: "var(--text-muted)", "stroke-width": 1, "stroke-dasharray": "5 4" }, svg);
  el("text", { x: M.l + iw, y: Y2(1) - 5, "text-anchor": "end", class: "band-label" }, svg).textContent = "1.0 跌破线";
  el("text", { x: M.l, y: P2.t - 12, class: "panel-title" }, svg).textContent = "比值 = 沪深300全收益 ÷ 二级债基";
  const span = (t1 - t0) / 3.156e10, every = [1, 2, 4, 5].find(s => iw / span * s >= 44) || 5;
  for (let y = c.xs[0].getFullYear() + 1; y <= c.xs.at(-1).getFullYear(); y++)
    if (y % every === 0) el("text", { x: X(new Date(y, 0, 1)), y: H - 6, "text-anchor": "middle" }, g).textContent = y;
  const path = (a, Y) => a.map((v, i) => (i ? "L" : "M") + X(c.xs[i]).toFixed(1) + "," + Y(v).toFixed(1)).join("");
  el("path", { d: path(c.bf, Y1), fill: "none", stroke: "var(--text-secondary)", "stroke-width": 2 }, svg);
  el("path", { d: path(c.eq, Y1), fill: "none", stroke: "var(--s-csi)", "stroke-width": 2 }, svg);
  const clip = el("clipPath", { id: "v1clip" }, el("defs", {}, svg));
  el("rect", { x: 0, y: P2.t, width: W, height: P2.h }, clip);
  el("path", { d: path(c.R, Y2), fill: "none", stroke: "var(--text-primary)", "stroke-width": 2, "clip-path": "url(#v1clip)" }, svg);
  const iMax = c.R.indexOf(sorted.at(-1));
  if (sorted.at(-1) > hi2) el("text", { x: X(c.xs[iMax]) + 6, y: P2.t + 10, class: "band-label" }, svg).textContent = `↑ 最高 ${sorted.at(-1).toFixed(1)}`;
  if (!narrow) {
    el("text", { x: M.l + iw + 6, y: Y1(c.eq.at(-1)) + 4, class: "panel-key" }, svg).textContent = Math.round(c.eq.at(-1));
    el("text", { x: M.l + iw + 6, y: Y1(c.bf.at(-1)) + 4, class: "panel-key" }, svg).textContent = Math.round(c.bf.at(-1));
  }
  let lastLabel = -Infinity; // 相邻底部太近时只标前一个，避免标签重叠
  for (const b of VERIFY_BOTTOMS) {
    const i = c.d.findIndex(s => s >= b);
    if (i <= 0) continue;
    const y = Math.max(P2.t, Math.min(P2.t + P2.h, Y2(c.R[i])));
    el("circle", { cx: X(c.xs[i]), cy: y, r: 4, fill: "var(--surface-1)", stroke: "var(--text-primary)", "stroke-width": 1.5 }, svg);
    if (!narrow && X(c.xs[i]) - lastLabel > 48) {
      el("text", { x: X(c.xs[i]), y: y + 15, "text-anchor": "middle", class: "band-label" }, svg).textContent = b.slice(0, 7);
      lastLabel = X(c.xs[i]);
    }
  }
  $("v1-bf-legend").textContent = `二级债基指数（${VERIFY_SCEN_NAME[verifyState.scen]}）`;
  for (const x of c.crosses) {
    const cx = X(c.xs[x.i]), cy = Y2(1);
    el("path", { d: `M${cx - 5},${cy - 9}L${cx + 5},${cy - 9}L${cx},${cy - 1}Z`, fill: "var(--s-csi)" }, svg);
  }
  const cross = el("line", { y1: P1.t, y2: P2.t + P2.h, stroke: "var(--text-muted)", "stroke-width": 1 }, svg);
  const dots = ["var(--s-csi)", "var(--text-secondary)", "var(--text-primary)"].map(f => el("circle", { r: 3.5, fill: f, stroke: "var(--surface-1)", "stroke-width": 2 }, svg));
  let cur = c.d.length - 1;
  const select = k => {
    cur = k;
    const x = X(c.xs[k]);
    cross.setAttribute("x1", x); cross.setAttribute("x2", x);
    [[c.eq[k], Y1], [c.bf[k], Y1], [c.R[k], Y2]].forEach(([v, Y], j) => { dots[j].setAttribute("cx", x); dots[j].setAttribute("cy", Y(v)); });
    dots[2].setAttribute("visibility", Y2(c.R[k]) >= P2.t ? "visible" : "hidden");
    ro.textContent = "";
    h("div", { className: "d", textContent: c.d[k] + (k === c.d.length - 1 ? "（最新）" : "") }, ro);
    for (const [col, val, name] of [["var(--s-csi)", Math.round(c.eq[k]).toLocaleString("en-US"), "沪深300全收益"],
      ["var(--text-secondary)", Math.round(c.bf[k]).toLocaleString("en-US"), `二级债基（${VERIFY_SCEN_NAME[verifyState.scen]}）`],
      ["var(--text-primary)", c.R[k].toFixed(2), c.R[k] < 1 ? "比值（低于 1：处于跌破状态）" : "比值"]]) {
      const row = h("div", { className: "row" }, ro);
      h("i", {}, row).style.background = col;
      h("b", { textContent: val }, row);
      h("em", { textContent: name }, row);
      h("small", {}, row);
    }
  };
  const pick = e => {
    const r = svg.getBoundingClientRect(), t = t0 + ((e.clientX - r.left) * W / r.width - M.l) / iw * (t1 - t0);
    let k = 0;
    c.xs.forEach((d, i) => { if (Math.abs(d - t) < Math.abs(c.xs[k] - t)) k = i; });
    select(k);
  };
  svg.onpointerdown = pick;
  svg.onpointermove = pick;
  svg.onkeydown = e => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    select(Math.max(0, Math.min(c.d.length - 1, cur + (e.key === "ArrowRight" ? 1 : -1))));
  };
  select(cur);
  $("v1-sum").textContent = verifySummary(c, verifyState.base);
}
// 板块初始化：结论、基准日切换按钮、文档链接（只做一次）
function initVerify(narrow) {
  $("v1-verdict").textContent = VERIFY_VERDICT;
  $("v1-doc").href = VERIFY_DOC;
  const segs = [["v1-base", VERIFY_BASES, "base"], ["v1-scen", VERIFY_SCENARIOS, "scen"]];
  for (const [id, items, field] of segs) {
    const box = $(id);
    for (const [label, v] of items) {
      const b = h("button", { type: "button", textContent: label }, box);
      b.setAttribute("aria-pressed", String(verifyState[field] === v));
      b.onclick = () => { verifyState[field] = v; [...box.children].forEach(x => x.setAttribute("aria-pressed", String(x === b))); renderVerify(narrow); };
    }
  }
}
