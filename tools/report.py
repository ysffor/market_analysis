# 计算分析文档里的所有数字，并回填到 ANALYSIS.md 中 <!-- AUTO:名称 --> … <!-- /AUTO:名称 --> 标记之间；
# 同时逐条复核文档结论所依赖的数据条件，不成立的标 ✗，提示需要人工修改结论。
# Compute every number in the analysis doc and refill the AUTO blocks in ANALYSIS.md;
# re-check each data condition the written conclusions depend on and flag failures with ✗.
# 用法 | usage: python -I report.py <raw 目录> <data.json> <ANALYSIS.md>
import bisect, csv, datetime, json, re, sys
import numpy as np

RAW, DATA_JSON, DOC = sys.argv[1:4]
THIS_YEAR = datetime.date.today().year

# 代表性事件：名称、起、止、归类。新增事件只改这里，文档表格会自动更新
# Episodes: name, start, end, category. Add new events here only
EPISODES = [
    ("2008 雷曼破产", "2008-09-10", "2008-11-26", "金融风险"),
    ("2014-15 油价崩盘", "2014-06-20", "2015-01-30", "油价/地缘"),
    ("2018-12→2019-09 贸易战、美联储转向", "2018-12-01", "2019-09-30", "贸易关系"),
    ("2019-09 回购利率飙升", "2019-09-10", "2019-12-31", "管道事件"),
    ("2020-03 疫情冲击", "2020-02-19", "2020-04-15", "金融风险"),
    ("2022 俄乌冲突、油价上涨", "2022-02-18", "2022-06-10", "油价/地缘 + 美联储加息"),
    ("2023-03 硅谷银行", "2023-03-08", "2023-03-29", "金融风险"),
    ("2023 债务上限后回补 TGA", "2023-06-01", "2023-10-25", "财政"),
    ("2025-04 关税冲击", "2025-04-01", "2025-04-30", "贸易关系（含缴税季）"),
]


def load(name):
    k, v = [], []
    for r in csv.DictReader(open(f"{RAW}/{name}.csv")):
        if r[name] not in ("", "."):
            k.append(r["observation_date"]); v.append(float(r[name]))
    return k, v


SER = {n: load(n) for n in ("DGS10", "DFII10", "T10YIE", "DCOILWTICO", "DTWEXBGS", "WALCL", "WTREGEN", "RRPONTSYD")}


def asof(name, d):
    k, v = SER[name]
    i = bisect.bisect_right(k, d) - 1
    return v[i] if i >= 0 else np.nan


def netliq_bn(d):  # 十亿美元 | $bn
    w, t, r = asof("WALCL", d) / 1e3, asof("WTREGEN", d) / 1e3, asof("RRPONTSYD", d)
    return w, t, (0 if np.isnan(r) else r)


# ---------- 15 天采样数据（与页面同一份） | 15-day sampled data (same as the page) ----------
D = json.load(open(DATA_JSON))
dates = D["dates"]
S = {k: np.array([np.nan if x is None else x for x in D[k]], float) for k in ("gold", "oil", "y10", "real", "dxy", "netliq")}
yr = np.array([int(d[:4]) for d in dates])
REGIMES = [(2007, THIS_YEAR), (2007, 2019), (2020, 2021), (2022, THIS_YEAR)]


def chg(x, h, log):
    return (np.log(x[h:]) - np.log(x[:-h])) if log else (x[h:] - x[:-h])


def corr_block():
    out, keep = [], {}
    for h, lab in ((6, "约 3 个月变化"), (24, "约 1 年变化")):
        c = {"gold": chg(S["gold"], h, 1), "oil": chg(S["oil"], h, 1), "y10": chg(S["y10"], h, 0),
             "nl": chg(S["netliq"], h, 1), "dxy": chg(S["dxy"], h, 1), "real": chg(S["real"], h, 0)}
        y = yr[h:]
        out.append(f"\n**{lab}**\n")
        out.append("| 时段 | 流动性 vs 黄金 | vs 原油 | vs 10Y 收益率 | 三者合起来的 R² | 美元指数 vs 黄金 | 美元指数 vs 原油 | 实际利率 vs 黄金 |")
        out.append("|---|---|---|---|---|---|---|---|")
        for lo, hi in REGIMES:
            m = (y >= lo) & (y <= hi)
            for k in c:
                m &= ~np.isnan(c[k])
            r = lambda a, b: np.corrcoef(c[a][m], c[b][m])[0, 1]
            X = np.column_stack([np.ones(m.sum()), c["gold"][m], c["oil"][m], c["y10"][m]])
            beta, *_ = np.linalg.lstsq(X, c["nl"][m], rcond=None)
            r2 = 1 - (c["nl"][m] - X @ beta).var() / c["nl"][m].var()
            row = dict(gold=r("nl", "gold"), oil=r("nl", "oil"), y10=r("nl", "y10"), r2=r2,
                       dxy_gold=r("dxy", "gold"), dxy_oil=r("dxy", "oil"), real_gold=r("real", "gold"))
            keep[(h, lo, hi)] = row
            out.append(f"| {lo}–{hi} | {row['gold']:+.2f} | {row['oil']:+.2f} | {row['y10']:+.2f} | {row['r2']*100:.0f}% | "
                       f"{row['dxy_gold']:+.2f} | {row['dxy_oil']:+.2f} | {row['real_gold']:+.2f} |")
    return "\n".join(out), keep


# ---------- 周度领先滞后 | weekly lead-lag ----------
LAGS = [-26, -13, -8, -4, 0, 4, 8, 13, 26]


def leadlag_block():
    wk, wv = SER["WALCL"]
    W = np.array(wv)
    T = np.array([asof("WTREGEN", d) for d in wk])
    R = np.nan_to_num(np.array([asof("RRPONTSYD", d) for d in wk]))
    RY = np.array([asof("DFII10", d) for d in wk])
    NL = W / 1e3 - T / 1e3 - R
    y = np.array([int(d[:4]) for d in wk])[13:]
    dNL = np.log(NL[13:]) - np.log(NL[:-13])
    dRY = RY[13:] - RY[:-13]

    def xc(a, b, lag):
        if lag > 0: a, b = a[:-lag], b[lag:]
        elif lag < 0: a, b = a[-lag:], b[:lag]
        m = ~np.isnan(a) & ~np.isnan(b)
        return np.corrcoef(a[m], b[m])[0, 1]

    head = " | ".join(("同期" if L == 0 else f"实际利率领先 {-L} 周" if L < 0 else f"流动性领先 {L} 周") for L in LAGS)
    out = [f"| 时段 | {head} |", "|---|" + "---|" * len(LAGS)]
    keep = {}
    for lo, hi in ((2008, THIS_YEAR), (2008, 2019), (2020, 2021), (2022, THIS_YEAR)):
        m = (y >= lo) & (y <= hi)
        vals = [xc(dNL[m], dRY[m], L) for L in LAGS]
        keep[(lo, hi)] = dict(zip(LAGS, vals))
        out.append(f"| {lo}–{hi} | " + " | ".join(f"{v:+.2f}" for v in vals) + " |")
    return "\n".join(out), keep


# ---------- 事件拆解 | episode decomposition ----------
def episodes_block():
    out = ["| 事件 | 类别 | 实际利率 | 名义收益率 | 通胀预期 | 美元 | 油价 | 净流动性 | 总资产 | −TGA | −逆回购 |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    keep = {}
    for name, a, b, cat in EPISODES:
        if b > SER["WALCL"][0][-1]:
            continue
        g = lambda n: asof(n, b) - asof(n, a)
        pc = lambda n: (asof(n, b) / asof(n, a) - 1) * 100
        (w0, t0, r0), (w1, t1, r1) = netliq_bn(a), netliq_bn(b)
        dW, dT, dR = w1 - w0, -(t1 - t0), -(r1 - r0)
        keep[name] = dict(nl=dW + dT + dR, fed=dW, tga=dT, rrp=dR)
        out.append(f"| {name}（{a} → {b}） | {cat} | {g('DFII10'):+.2f} | {g('DGS10'):+.2f} | {g('T10YIE'):+.2f} | "
                   f"{pc('DTWEXBGS'):+.1f}% | {pc('DCOILWTICO'):+.0f}% | **{dW+dT+dR:+,.0f}** | {dW:+,.0f} | {dT:+,.0f} | {dR:+,.0f} |")
    out.append("\n利率类单位为百分点；美元、油价为涨跌幅；流动性各项单位为十亿美元，正数表示增加流动性，三项相加等于净流动性。")
    return "\n".join(out), keep


# ---------- 当前读数 | latest snapshot ----------
def snapshot_block():
    rows = [("黄金", "gold", "美元/盎司", 0), ("WTI 原油", "oil", "美元/桶", 2), ("10Y 名义收益率", "y10", "%", 2),
            ("10Y 实际利率", "real", "%", 2), ("10Y 通胀预期", "be", "%", 2), ("美元指数（广义）", "dxy", "", 1),
            ("净流动性", "netliq", "万亿美元", 2), ("美联储总资产", "walcl", "万亿美元", 2), ("TGA", "tga", "万亿美元", 2),
            ("逆回购", "rrp", "十亿美元", 1)]
    out = ["| 指标 | 最新值 | 约一年前 | 数据截至 |", "|---|---|---|---|"]
    for name, k, unit, d in rows:
        v = [x * 1000 for x in D[k]] if k == "rrp" else D[k]  # 逆回购余额已很小，改用十亿美元显示
        out.append(f"| {name} | {v[-1]:,.{d}f} {unit} | {v[-25]:,.{d}f} {unit} | {D['asof'].get(k, D['asof'].get('walcl'))} |")
    nl = np.array(D["netliq"], float)
    out.append(f"\n净流动性 20 年内高点 {nl.max():.2f} 万亿美元（{dates[int(nl.argmax())]}）。")
    return "\n".join(out)


# ---------- 结论复核 | conclusion checks ----------
def checks_block(cr, ll, ep):
    full, old, new = cr[(6, 2007, THIS_YEAR)], cr[(6, 2007, 2019)], cr[(6, 2022, THIS_YEAR)]
    l_old, l_new = ll[(2008, 2019)], ll[(2022, THIS_YEAR)]
    oil = ep.get("2014-15 油价崩盘"); u22 = ep.get("2022 俄乌冲突、油价上涨")
    items = [
        ("发现 1", "黄金、原油、10Y 收益率合起来解释不了净流动性变化（全样本 3 个月 R² < 30%）", full["r2"] < 0.3, f"R² = {full['r2']*100:.0f}%"),
        ("发现 1", "2007–2019 黄金与实际利率明显反向（相关 ≤ −0.5）", old["real_gold"] <= -0.5, f"{old['real_gold']:+.2f}"),
        ("发现 1", f"2022 年后黄金与实际利率的关系弱于 2007–2019", abs(new["real_gold"]) < abs(old["real_gold"]), f"{new['real_gold']:+.2f} vs {old['real_gold']:+.2f}"),
        ("发现 2", "2008–2019 实际利率领先约 1 个月时正相关（> +0.2）", l_old[-4] > 0.2, f"{l_old[-4]:+.2f}"),
        ("发现 2", "2008–2019 流动性领先约一个季度时负相关（< −0.15）", l_old[13] < -0.15, f"{l_old[13]:+.2f}"),
        ("发现 2", f"2022–{THIS_YEAR} 同期反向最强（同期相关 < −0.2）", l_new[0] < -0.2 and abs(l_new[0]) >= max(abs(v) for v in l_new.values()) - 1e-9, f"同期 {l_new[0]:+.2f}"),
        ("发现 3", "2014-15 油价崩盘时净流动性几乎不动（变化绝对值 < 2000 亿美元）", oil is not None and abs(oil["nl"]) < 200, f"{oil['nl']:+,.0f} 十亿" if oil else "无数据"),
        ("发现 3", "2022 净流动性下降主要来自逆回购（占比 > 60%）", u22 is not None and u22["rrp"] / u22["nl"] > 0.6, f"{u22['rrp'] / u22['nl'] * 100:.0f}%" if u22 else "无数据"),
    ]
    out = ["| 结论 | 依赖的数据条件 | 当前数值 | 状态 |", "|---|---|---|---|"]
    bad = 0
    for sec, text, ok, val in items:
        bad += not ok
        out.append(f"| {sec} | {text} | {val} | {'✓' if ok else '✗ 需要复核结论'} |")
    out.append(f"\n{'全部成立。' if not bad else f'有 {bad} 条不成立：请按对应发现修改正文结论，并在变更记录里写明。'}")
    return "\n".join(out), bad


def fill(doc, name, body):
    pat = re.compile(rf"(<!-- AUTO:{name} -->\n).*?(<!-- /AUTO:{name} -->)", re.S)
    if not pat.search(doc):
        sys.exit(f"ANALYSIS.md 里缺少 AUTO:{name} 标记")
    return pat.sub(lambda m: m.group(1) + "\n" + body.strip("\n") + "\n\n" + m.group(2), doc)


cb, cr = corr_block()
lb, ll = leadlag_block()
eb, ep = episodes_block()
kb, bad = checks_block(cr, ll, ep)
doc = open(DOC, encoding="utf-8").read()
doc = fill(doc, "updated", f"数据截至 {dates[-1]}（各序列最新日期见“当前读数”），由 `tools/update.sh` 于 {datetime.date.today()} 生成。")
doc = fill(doc, "snapshot", snapshot_block())
doc = fill(doc, "corr", cb)
doc = fill(doc, "leadlag", lb)
doc = fill(doc, "episodes", eb)
doc = fill(doc, "checks", kb)
open(DOC, "w", encoding="utf-8", newline="\n").write(doc)
print(f"ANALYSIS.md 已更新；结论复核：{'全部成立' if not bad else f'{bad} 条不成立，需要人工修改结论'}")
