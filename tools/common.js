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
