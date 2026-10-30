# 人民币流动性（B）及美元收紧（A）对它的影响（C）：建月度面板、收紧指数、回归与渠道分解、事件研究，
# 回填 docs/ANALYSIS.md 中 <!-- AUTO:cn_* --> 区块并复核结论依赖的数据条件。
# RMB liquidity (B) and the impact of USD tightening (A) on it (C): monthly panel, tightness indices, regressions with
# Newey-West errors, channel decomposition and Fed-tightening event study; refills cn_* AUTO blocks in ANALYSIS.md.
# 用法 | usage: python -I analysis_cn.py <raw 目录> <docs/ANALYSIS.md> [<输出分析报告页的图表数据 build/cn.json>]
import bisect, csv, datetime, json, math, re, sys
import numpy as np

RAW, DOC = sys.argv[1:3]
PAGE = sys.argv[3] if len(sys.argv) > 3 else None
START = "2010-01"
H = 6            # 变化窗口：6 个月
NW_LAG = 6       # Newey-West 滞后阶数（与重叠窗口长度一致）


# ---------- 读数据 ----------
def fred(name):
    out = {}
    for r in csv.DictReader(open(f"{RAW}/{name}.csv")):
        if r[name] not in ("", "."):
            out[r["observation_date"]] = float(r[name])
    return out


def em(name):
    return json.load(open(f"{RAW}/cn/{name}.json", encoding="utf-8"))


def monthly_avg(daily):
    acc = {}
    for d, v in daily.items():
        if v is None:
            continue
        acc.setdefault(d[:7], []).append(v)
    return {m: sum(v) / len(v) for m, v in acc.items()}


def monthly_last(daily):
    out = {}
    for d in sorted(daily):
        if daily[d] is not None:
            out[d[:7]] = daily[d]
    return out


F = {n: fred(n) for n in ("DFII10", "DGS10", "DTWEXBGS", "WALCL", "WTREGEN", "RRPONTSYD", "DEXCHUS", "DFF")}
repo = json.load(open(f"{RAW}/cn/repo.json"))
shibor = json.load(open(f"{RAW}/cn/shibor.json"))
fnum = lambda x: None if x in (None, "", "---") else float(x)
yields = {r["SOLAR_DATE"][:10]: r for r in em("bond_yields")}
S = {  # 月度序列：月份 "YYYY-MM" -> 值
    "real10y": monthly_avg(F["DFII10"]),
    "dxy": monthly_avg(F["DTWEXBGS"]),
    "dff": monthly_avg(F["DFF"]),
    "us10y": monthly_avg(F["DGS10"]),
    "usdcny": monthly_avg(F["DEXCHUS"]),
    "fr007": monthly_avg({d: fnum(v["FR007"]) for d, v in repo.items()}),
    "dr007": monthly_avg({d: fnum(v["FDR007"]) for d, v in repo.items()}),
    "shibor3m": monthly_avg({d: fnum(v["3M"]) for d, v in shibor.items()}),
    "cn10y": monthly_avg({d: r.get("EMM00166466") for d, r in yields.items()}),
}
# 美联储净流动性（十亿美元，周度取月均）
wk = sorted(F["WALCL"])
tga, rrp = sorted(F["WTREGEN"]), sorted(F["RRPONTSYD"])
asof = lambda s, keys, d: s[keys[bisect.bisect_right(keys, d) - 1]] if bisect.bisect_right(keys, d) else None
S["netliq"] = monthly_avg({d: F["WALCL"][d] / 1e3 - asof(F["WTREGEN"], tga, d) / 1e3 - (asof(F["RRPONTSYD"], rrp, d) or 0) for d in wk})
mon = lambda r: r["REPORT_DATE"][:7]
S["m2"] = {mon(r): r["BASIC_CURRENCY_SAME"] for r in em("money_supply") if r["BASIC_CURRENCY_SAME"] is not None}
S["m1"] = {mon(r): r["CURRENCY_SAME"] for r in em("money_supply") if r["CURRENCY_SAME"] is not None}
loans = {mon(r): r["RMB_LOAN"] for r in em("rmb_loan") if r["RMB_LOAN"] is not None}
S["fxres"] = {mon(r): r["FOREX"] / 10 for r in em("fx_reserves") if r["FOREX"] is not None}   # 亿美元 -> 十亿美元
S["pmi"] = {mon(r): r["MAKE_INDEX"] for r in em("pmi") if r["MAKE_INDEX"] is not None}
S["cpi"] = {mon(r): r["NATIONAL_SAME"] for r in em("cpi") if r["NATIONAL_SAME"] is not None}
# 存款准备金率（大型金融机构，按生效日）与政策贷款利率（2019-08-20 前为 1 年期贷款基准利率，之后为 1 年期 LPR）
cnd = lambda s: f"{s[:4]}-{s[5:7]}-{s[8:10]}"
rrr_ev = sorted((cnd(r["TRADE_DATE"]), r["INTEREST_RATE_BA"]) for r in em("rrr") if r.get("INTEREST_RATE_BA") is not None)
lpr_ev = sorted((r["TRADE_DATE"][:10], r["LPR1Y"] if r["TRADE_DATE"][:10] >= "2019-08-20" and r.get("LPR1Y") else r["RATE_1"])
                for r in em("lpr") if (r.get("LPR1Y") or r.get("RATE_1")))


def step_month(events, months):
    out, keys = {}, [e[0] for e in events]
    for m in months:
        end = f"{m}-31"
        i = bisect.bisect_right(keys, end) - 1
        if i >= 0:
            out[m] = events[i][1]
    return out


# 月份轴：2010-01 到所有核心序列都有数据的最后一个月
core = ["real10y", "dxy", "dff", "netliq", "usdcny", "fr007", "shibor3m", "cn10y", "us10y", "m2", "m1", "fxres", "pmi", "cpi"]
last = min(max(S[k]) for k in core)
months, y, mth = [], 2010, 1
while f"{y}-{mth:02d}" <= last:
    months.append(f"{y}-{mth:02d}")
    y, mth = (y + 1, 1) if mth == 12 else (y, mth + 1)
S["rrr"] = step_month(rrr_ev, months)
S["policy"] = step_month(lpr_ev, months)
# 新增人民币贷款：过去 12 个月合计的同比增速
lk = sorted(loans)
S["loan12"] = {}
for m in lk:
    i = lk.index(m)
    if i >= 23:
        cur, prev = sum(loans[k] for k in lk[i - 11:i + 1]), sum(loans[k] for k in lk[i - 23:i - 11])
        S["loan12"][m] = (cur / prev - 1) * 100
# 净流动性同比（%）
nk = sorted(S["netliq"])
S["netliq_yoy"] = {m: (S["netliq"][m] / S["netliq"][nk[nk.index(m) - 12]] - 1) * 100 for m in nk if nk.index(m) >= 12}
S["spread"] = {m: S["cn10y"][m] - S["us10y"][m] for m in months if m in S["cn10y"] and m in S["us10y"]}

V = {k: np.array([S[k].get(m, np.nan) for m in months], float) for k in list(S)}
N = len(months)


def z(x):
    return (x - np.nanmean(x)) / np.nanstd(x)


# 收紧指数：各指标标准化后取平均，数值越大越紧
IDX = {
    "A_price": (["real10y", "dxy", "dff"], [1, 1, 1], "美元价格层：10 年期实际利率、美元指数、联邦基金利率"),
    "A_qty": (["netliq_yoy"], [-1], "美元数量层：美联储净流动性同比（取负）"),
    "B_price": (["fr007", "shibor3m", "cn10y"], [1, 1, 1], "人民币价格层：FR007、SHIBOR 3 个月、10 年期国债"),
    "B_qty": (["m2", "m1", "loan12"], [-1, -1, -1], "人民币数量层：M2 同比、M1 同比、12 个月新增贷款同比（均取负）"),
}
for k, (cols, sg, _) in IDX.items():
    V[k] = np.nanmean(np.vstack([s * z(V[c]) for c, s in zip(cols, sg)]), axis=0)


def d(x, h=H):
    out = np.full(N, np.nan)
    out[h:] = x[h:] - x[:-h]
    return out


def dlog(x, h=H):
    out = np.full(N, np.nan)
    out[h:] = (np.log(x[h:]) - np.log(x[:-h])) * 100
    return out


def lagged(x, L):
    out = np.full(N, np.nan)
    out[L:] = x[:N - L] if L else x
    return out


def ols(yv, cols):
    """OLS + Newey-West 标准误。返回 (系数, 标准误, R², 样本数)，自动剔除缺失"""
    X = np.column_stack([np.ones(N)] + cols)
    m = ~np.isnan(yv) & ~np.isnan(X).any(axis=1)
    X, Y = X[m], yv[m]
    n, k = X.shape
    XtX_inv = np.linalg.inv(X.T @ X)
    b = XtX_inv @ X.T @ Y
    e = Y - X @ b
    Sx = (X * e[:, None]).T @ (X * e[:, None])
    for l in range(1, NW_LAG + 1):
        w = 1 - l / (NW_LAG + 1)
        G = (X[l:] * e[l:, None]).T @ (X[:-l] * e[:-l, None])
        Sx += w * (G + G.T)
    se = np.sqrt(np.diag(XtX_inv @ Sx @ XtX_inv))
    r2 = 1 - e.var() / Y.var()
    return b, se, r2, n


CTRL = [d(V["pmi"]), d(V["cpi"])]
fmt = lambda v, dgt=2: "—" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:+.{dgt}f}"
star = lambda b, se: "**" if abs(b / se) >= 2.58 else "*" if abs(b / se) >= 1.96 else ""


# ---------- B：趋势 ----------
def pct_rank(x, i):
    v = x[~np.isnan(x)]
    return (v <= x[i]).mean() * 100


def b_trend():
    lastm = months[-1]
    i = N - 1
    rows = [("FR007（月均）", "fr007", "%", 2), ("SHIBOR 3 个月", "shibor3m", "%", 2), ("10 年期国债", "cn10y", "%", 2),
            ("M2 同比", "m2", "%", 1), ("M1 同比", "m1", "%", 1), ("12 个月新增贷款同比", "loan12", "%", 1),
            ("存款准备金率（大型银行）", "rrr", "%", 1), ("1 年期政策贷款利率（LPR / 基准利率）", "policy", "%", 2),
            ("外汇储备", "fxres", "十亿美元", 0), ("美元兑人民币", "usdcny", "", 4), ("中美 10 年期利差（中 − 美）", "spread", "百分点", 2)]
    out = [f"截至 {lastm}（月度数据的最新完整月份），各指标水平、近 6 个月和 12 个月的变化，以及当前水平在 2010 年以来的历史分位：\n",
           "| 指标 | 最新 | 6 个月变化 | 12 个月变化 | 历史分位 |", "|---|---|---|---|---|"]
    for name, k, u, dg in rows:
        x = V[k]
        out.append(f"| {name} | {x[i]:,.{dg}f} {u} | {fmt(x[i] - x[i - 6], dg)} | {fmt(x[i] - x[i - 12], dg)} | {pct_rank(x, i):.0f}% |")
    return "\n".join(out)


def idx_table():
    out = ["| 年份 | 美元价格层 | 美元数量层 | 人民币价格层 | 人民币数量层 |", "|---|---|---|---|---|"]
    years = sorted({m[:4] for m in months})
    for yy in years:
        sel = [j for j, m in enumerate(months) if m[:4] == yy]
        out.append(f"| {yy}{'（至 ' + months[-1][5:] + ' 月）' if yy == months[-1][:4] else ''} | " +
                   " | ".join(f"{np.nanmean(V[k][sel]):+.2f}" for k in ("A_price", "A_qty", "B_price", "B_qty")) + " |")
    out.append("\n指数为各指标标准化（2010 年至今均值 0、标准差 1）后的平均，数值越大越紧。构成：")
    for k, (_, _, desc) in IDX.items():
        out.append(f"- {desc}")
    out.append(f"\n两组指数的相关（月度水平）：美元价格层与人民币价格层 {np.corrcoef(*[V[k][~np.isnan(V['A_price']) & ~np.isnan(V['B_price'])] for k in ('A_price', 'B_price')])[0, 1]:+.2f}；"
               f"美元价格层与人民币数量层 {np.corrcoef(*[V[k][~np.isnan(V['A_price']) & ~np.isnan(V['B_qty'])] for k in ('A_price', 'B_qty')])[0, 1]:+.2f}。")
    return "\n".join(out)


# ---------- C1：整体解释力 ----------
def c_overall():
    out = ["因变量和自变量都是 6 个月变化；控制变量为中国制造业 PMI 和 CPI 同比的 6 个月变化。"
           "\"新增解释力\"是加入美元指数后 R² 比只用控制变量时提高了多少；系数为美元指数变化 1 个单位（约 1 个标准差）时人民币指数的变化。"
           "\\* 表示 5% 水平显著，\\*\\* 表示 1% 水平显著（Newey-West 标准误）。\n",
           "| 人民币指数 | 美元指数 | 滞后 0 个月：系数 / 新增解释力 | 滞后 3 个月 | 滞后 6 个月 | 滞后 12 个月 |", "|---|---|---|---|---|---|"]
    keep = {}
    base = {}
    for bk in ("B_price", "B_qty"):
        base[bk] = ols(d(V[bk]), CTRL)[2]
        for ak in ("A_price", "A_qty"):
            cells = []
            for L in (0, 3, 6, 12):
                yv, xv = d(V[bk]), lagged(d(V[ak]), L)
                b, se, r2, n = ols(yv, [xv] + CTRL)
                r2c = ols(np.where(np.isnan(xv), np.nan, yv), CTRL)[2]
                keep[(bk, ak, L)] = (b[1], se[1], r2 - r2c)
                cells.append(f"{b[1]:+.2f}{star(b[1], se[1])} / {(r2 - r2c)*100:.0f}%")
            out.append(f"| {'人民币价格层' if bk == 'B_price' else '人民币数量层'} | {'美元价格层' if ak == 'A_price' else '美元数量层'} | " + " | ".join(cells) + " |")
    out.append(f"\n只用控制变量（PMI、CPI）时的 R²：人民币价格层 {base['B_price']*100:.0f}%，人民币数量层 {base['B_qty']*100:.0f}%。")
    return "\n".join(out), keep, base


# ---------- C2：渠道 ----------
def c_channels():
    out, keep = [], {}
    # (1) A → 汇率、外汇储备、利差
    out.append("**第一段：美元收紧 → 汇率、外汇储备、中美利差**（自变量为美元价格层的 6 个月变化，控制中国 PMI）\n")
    out.append("| 被解释变量（6 个月变化） | 系数 | 标准误 | R² | 含义 |")
    out.append("|---|---|---|---|---|")
    targets = [("美元兑人民币（%，正数为人民币贬值）", dlog(V["usdcny"]), "usdcny"),
               ("外汇储备（十亿美元）", d(V["fxres"]), "fxres"),
               ("中美 10 年期利差（百分点）", d(V["spread"]), "spread"),
               ("中国 10 年期国债（百分点）", d(V["cn10y"]), "cn10y"),
               ("FR007（百分点）", d(V["fr007"]), "fr007")]
    for name, yv, key in targets:
        b, se, r2, n = ols(yv, [d(V["A_price"]), d(V["pmi"])])
        keep[key] = (b[1], se[1], r2)
        out.append(f"| {name} | {b[1]:+.3f}{star(b[1], se[1])} | {se[1]:.3f} | {r2*100:.0f}% | 美元价格层收紧 1 个单位时的平均变化 |")
    # (2) 利差变化中有多少来自美方
    ds, dus, dcn = d(V["spread"]), d(V["us10y"]), d(V["cn10y"])
    m = ~np.isnan(ds)
    sh_us = np.cov(-dus[m], ds[m])[0, 1] / ds[m].var(ddof=1)
    keep["share_us"] = sh_us
    out.append(f"\n**中美利差的变化来自哪一方**：利差（中 − 美）的 6 个月变化中，约 **{sh_us*100:.0f}%** 来自美国国债收益率的变化，"
               f"约 {100 - sh_us*100:.0f}% 来自中国国债收益率的变化（按协方差分解）。")
    # (3) 汇率 → 人民币流动性
    out.append("\n**第二段：汇率压力 → 人民币流动性**（自变量为美元兑人民币过去 6 个月的涨跌幅，滞后 0 / 3 / 6 个月；控制 PMI、CPI）\n")
    out.append("| 被解释变量（6 个月变化） | 滞后 0 个月 | 滞后 3 个月 | 滞后 6 个月 |")
    out.append("|---|---|---|---|")
    for name, yv, key in (("人民币价格层", d(V["B_price"]), "B_price"), ("人民币数量层", d(V["B_qty"]), "B_qty"),
                          ("FR007（百分点）", d(V["fr007"]), "fr007"), ("10 年期国债（百分点）", d(V["cn10y"]), "cn10y")):
        cells = []
        for L in (0, 3, 6):
            b, se, r2, n = ols(yv, [lagged(dlog(V["usdcny"]), L)] + CTRL)
            keep[("fx", key, L)] = (b[1], se[1])
            cells.append(f"{b[1]:+.3f}{star(b[1], se[1])}")
        out.append(f"| {name} | " + " | ".join(cells) + " |")
    out.append("\n系数为人民币对美元每贬值 1% 时，各指标在之后的平均变化。")
    return "\n".join(out), keep


# ---------- C3：事件研究 ----------
def find_eps(series, th, min_len=2):
    """series 的 12 个月变化 ≥ th 的月份；间隔不超过 3 个月的合并为一段；只保留持续至少 min_len 个月的"""
    ch = d(series, 12)
    on = [not np.isnan(x) and x >= th for x in ch]
    eps, j = [], 0
    while j < N:
        if on[j]:
            k = j
            while k + 1 < N and (on[k + 1] or any(on[k + 1:k + 4])):
                k += 1
            if k - j + 1 >= min_len:
                eps.append((j, k))
            j = k + 1
        else:
            j += 1
    return eps


def episodes():
    """两种定义：加息期（联邦基金利率 12 个月累计上升 ≥ 0.5 个百分点）；美元走强期（美元价格层 12 个月上升 ≥ 0.4，约 0.8 个标准差）"""
    eps = [("加息期", a, b) for a, b in find_eps(V["dff"], 0.5)] + [("美元走强期", a, b) for a, b in find_eps(V["A_price"], 0.4)]
    return sorted(eps, key=lambda e: e[1])


def c_events():
    eps = episodes()
    cols = [("联邦基金利率", "dff", "pp", 2, None), ("美国实际利率", "real10y", "pp", 2, None), ("美元指数", "dxy", "%", 1, "pct"),
            ("美联储净流动性", "netliq", "%", 1, "pct"), ("美元兑人民币", "usdcny", "%", 1, "pct"), ("外汇储备", "fxres", "十亿美元", 0, None),
            ("中美利差", "spread", "pp", 2, None), ("FR007", "fr007", "pp", 2, None), ("中国 10 年期", "cn10y", "pp", 2, None),
            ("M2 同比", "m2", "pp", 1, None), ("12 个月新增贷款同比", "loan12", "pp", 1, None),
            ("存款准备金率", "rrr", "pp", 1, None), ("政策贷款利率", "policy", "pp", 2, None)]
    out = ["两种方式识别美元收紧期：**加息期**为联邦基金利率过去 12 个月累计上升至少 0.5 个百分点的月份；"
           "**美元走强期**为美元价格层过去 12 个月上升至少 0.4（约 0.8 个标准差）的月份。间隔不超过 3 个月的合并为一段，只保留持续 2 个月以上的。"
           "表中为每段期间（从开始前一个月到结束月）的变化，pp 为百分点。\n"]
    head = "| 指标 | " + " | ".join(f"{lab}<br>{months[a]} → {months[b]}" for lab, a, b in eps) + " |"
    out += [head, "|---|" + "---|" * len(eps)]
    keep = []
    for name, k, u, dg, how in cols:
        cells = []
        for _, a, b in eps:
            s, e = V[k][max(a - 1, 0)], V[k][b]
            v = (e / s - 1) * 100 if how == "pct" else e - s
            cells.append(f"{v:+,.{dg}f}{'%' if how == 'pct' else ''}")
        out.append(f"| {name}（{u}） | " + " | ".join(cells) + " |")
    for lab, a, b in eps:
        keep.append({k: (V[k][b] / V[k][max(a - 1, 0)] - 1) * 100 if how == "pct" else V[k][b] - V[k][max(a - 1, 0)]
                     for _, k, _, _, how in cols} | {"span": (months[a], months[b]), "label": lab})
    # 降准频率：收紧期内（两种定义的并集）与其余时间，按每年平均
    cut_dates = [e[0][:7] for i, e in enumerate(rrr_ev) if i and e[1] < rrr_ev[i - 1][1] and e[0][:7] >= START]
    in_ep = lambda m: any(months[a] <= m <= months[b] for _, a, b in eps)
    n_in = sum(in_ep(m) for m in months)
    c_in = sum(in_ep(m) for m in cut_dates)
    rate = (c_in / n_in * 12, (len(cut_dates) - c_in) / (N - n_in) * 12)
    out.append(f"\n降准频率：美元收紧期内（两种定义合并）平均每年 {rate[0]:.1f} 次，其余时间平均每年 {rate[1]:.1f} 次"
               f"（2010 年以来共 {len(cut_dates)} 次降准，其中 {c_in} 次发生在收紧期内）。")
    return "\n".join(out), keep, [(a, b) for _, a, b in eps], rate


# ---------- 稳健性 ----------
def c_robust():
    sub = {"全样本，6 个月变化": (None, None, 6), "全样本，12 个月变化": (None, None, 12),
           "2010–2016，6 个月变化": ("2010-01", "2016-12", 6), "2017 至今，6 个月变化": ("2017-01", None, 6)}
    tests = [("美元价格层 → 美元兑人民币（%）", lambda h: dlog(V["usdcny"], h), "A_price", 0),
             ("美元价格层 → 中美利差（pp）", lambda h: d(V["spread"], h), "A_price", 0),
             ("美元价格层 → 人民币价格层", lambda h: d(V["B_price"], h), "A_price", 0),
             ("美元价格层 → 人民币数量层", lambda h: d(V["B_qty"], h), "A_price", 0),
             ("美元数量层 → 人民币价格层（滞后 3 个月）", lambda h: d(V["B_price"], h), "A_qty", 3)]
    out = ["关键系数在不同窗口和不同时段下的表现（控制 PMI、CPI；括号内为 t 值）：\n",
           "| 关系 | " + " | ".join(sub) + " |", "|---|" + "---|" * len(sub)]
    keep = {}
    for name, yf, ak, L in tests:
        cells = []
        for sname, (a, b, h) in sub.items():
            yv = yf(h)
            mask = np.array([(a is None or m >= a) and (b is None or m <= b) for m in months])
            yv = np.where(mask, yv, np.nan)
            ctrl = [d(V["pmi"], h), d(V["cpi"], h)]
            bb, se, r2, n = ols(yv, [lagged(d(V[ak], h), L)] + ctrl)
            keep[(name, sname)] = (bb[1], se[1])
            cells.append(f"{bb[1]:+.2f}（{bb[1]/se[1]:+.1f}）")
        out.append(f"| {name} | " + " | ".join(cells) + " |")
    return "\n".join(out), keep


# ---------- 当前读数 ----------
def c_now():
    i = N - 1
    out = [f"截至 {months[-1]}：\n", "| 指数 | 当前 | 6 个月变化 | 12 个月变化 | 2010 年以来分位 |", "|---|---|---|---|---|"]
    for k, name in (("A_price", "美元价格层"), ("A_qty", "美元数量层"), ("B_price", "人民币价格层"), ("B_qty", "人民币数量层")):
        x = V[k]
        out.append(f"| {name} | {x[i]:+.2f} | {fmt(x[i] - x[i - 6])} | {fmt(x[i] - x[i - 12])} | {pct_rank(x, i):.0f}% |")
    return "\n".join(out)


# ---------- 影响有多大：汇总 ----------
def c_size(ov, ch):
    rows = [("美元兑人民币", ch["usdcny"], "%"), ("外汇储备", ch["fxres"], "十亿美元"), ("中美 10 年期利差", ch["spread"], "百分点"),
            ("中国 10 年期国债", ch["cn10y"], "百分点"), ("FR007", ch["fr007"], "百分点")]
    sd = np.nanstd(d(V["A_price"]))
    r_us = np.nanstd(d(V["real10y"]))
    out = [f"美元价格层的 6 个月变化，标准差为 {sd:.2f} 个单位，大致相当于美国 10 年期实际利率在 6 个月内变化 {r_us:.2f} 个百分点。"
           "下表按\"美元价格层收紧 1 个标准差\"换算：\n", "| 指标 | 平均变化 | 95% 区间 |", "|---|---|---|"]
    for name, (b, se, r2), u in rows:
        out.append(f"| {name} | {b*sd:+.2f} {u} | {((b-1.96*se)*sd):+.2f} 到 {((b+1.96*se)*sd):+.2f} |")
    bp = ov[("B_price", "A_price", 0)]
    bq = ov[("B_qty", "A_price", 0)]
    out.append(f"| 人民币价格层（同期，控制 PMI、CPI） | {bp[0]*sd:+.2f} 个单位 | {((bp[0]-1.96*bp[1])*sd):+.2f} 到 {((bp[0]+1.96*bp[1])*sd):+.2f} |")
    out.append(f"| 人民币数量层（同期，控制 PMI、CPI） | {bq[0]*sd:+.2f} 个单位 | {((bq[0]-1.96*bq[1])*sd):+.2f} 到 {((bq[0]+1.96*bq[1])*sd):+.2f} |")
    return "\n".join(out), sd


def fill(doc, name, body):
    pat = re.compile(rf"(<!-- AUTO:{name} -->\n).*?(<!-- /AUTO:{name} -->)", re.S)
    if not pat.search(doc):
        sys.exit(f"ANALYSIS.md 里缺少 AUTO:{name} 标记")
    return pat.sub(lambda m: m.group(1) + "\n" + body.strip("\n") + "\n\n" + m.group(2), doc)


tb = b_trend()
ib = idx_table()
ob, ov, base = c_overall()
chb, ch = c_channels()
evb, evk, eps, cut_rate = c_events()
szb, sd = c_size(ov, ch)
rb, rob = c_robust()
nb = c_now()


def checks():
    i = N - 1
    pr = lambda k: pct_rank(V[k], i)
    tval = lambda bse: bse[0] / bse[1]
    ch12 = lambda k: V[k][i] - V[k][i - 12]
    inc = [ov[(bk, ak, L)][2] for bk in ("B_price", "B_qty") for ak in ("A_price", "A_qty") for L in (0, 3, 6, 12)]
    ep_ok = all(e["rrr"] <= 0 and e["policy"] <= 0 for e in evk)
    rob_bp = [rob[("美元价格层 → 人民币价格层", s)] for s in ("全样本，6 个月变化", "全样本，12 个月变化", "2010–2016，6 个月变化", "2017 至今，6 个月变化")]
    fx_old, fx_new = rob[("美元价格层 → 美元兑人民币（%）", "2010–2016，6 个月变化")], rob[("美元价格层 → 美元兑人民币（%）", "2017 至今，6 个月变化")]
    items = [
        ("A 趋势", "美元价格层当前处于 2010 年以来 80% 分位以上（偏紧）", pr("A_price") >= 80, f"{pr('A_price'):.0f}%"),
        ("B 发现 1", "人民币价格层当前处于 2010 年以来最松的 10%", pr("B_price") <= 10, f"{pr('B_price'):.0f}%"),
        ("B 发现 1", "人民币数量层当前处于最紧的 20%，且 12 个月新增贷款同比为负", pr("B_qty") >= 80 and V["loan12"][i] < 0,
         f"{pr('B_qty'):.0f}%，贷款 {V['loan12'][i]:+.1f}%"),
        ("B 发现 2", "过去 12 个月存款准备金率和政策贷款利率都没有上调", ch12("rrr") <= 0 and ch12("policy") <= 0,
         f"准备金率 {ch12('rrr'):+.1f}，政策利率 {ch12('policy'):+.2f}"),
        ("C 发现 1", "美元价格层收紧时人民币贬值：系数为正且显著（t ≥ 2），R² ≥ 20%", ch["usdcny"][0] > 0 and tval(ch["usdcny"]) >= 2 and ch["usdcny"][2] >= 0.20,
         f"t = {tval(ch['usdcny']):.1f}，R² = {ch['usdcny'][2]*100:.0f}%"),
        ("C 发现 1", "美元价格层收紧时中美利差更负且显著；利差变化中美方贡献不低于 70%", ch["spread"][0] < 0 and tval(ch["spread"]) <= -2 and ch["share_us"] >= 0.70,
         f"t = {tval(ch['spread']):.1f}，美方 {ch['share_us']*100:.0f}%"),
        ("C 发现 1", "汇率渠道在 2017 年以后显著（t ≥ 2），2010–2016 年不显著", tval(fx_new) >= 2 and abs(tval(fx_old)) < 2,
         f"2017 后 t = {tval(fx_new):.1f}，之前 t = {tval(fx_old):.1f}"),
        ("C 发现 2", "美元价格层对中国 10 年期国债、FR007 的影响都不显著（t 的绝对值小于 2）", abs(tval(ch["cn10y"])) < 2 and abs(tval(ch["fr007"])) < 2,
         f"t = {tval(ch['cn10y']):.1f} / {tval(ch['fr007']):.1f}"),
        ("C 发现 2", "美元两个指数对人民币两个指数，各滞后期的新增解释力都不超过 15%", max(inc) <= 0.15, f"最高 {max(inc)*100:.0f}%"),
        ("C 发现 2", "美元价格层对人民币价格层在四种设定下都不显著（t 的绝对值小于 2）", all(abs(tval(x)) < 2 for x in rob_bp),
         "t = " + " / ".join(f"{tval(x):.1f}" for x in rob_bp)),
        ("C 发现 3", "每一段美元收紧期内，存款准备金率和政策贷款利率都没有上调", ep_ok, f"{len(evk)} 段"),
        ("C 当前", "过去 12 个月人民币对美元升值、外汇储备增加，即汇率渠道目前没有承压", ch12("usdcny") < 0 and ch12("fxres") > 0,
         f"美元兑人民币 {ch12('usdcny'):+.3f}，外汇储备 {ch12('fxres'):+.0f} 十亿美元"),
    ]
    out = ["| 对应 | 依赖的数据条件 | 当前数值 | 状态 |", "|---|---|---|---|"]
    bad = 0
    for sec, text, ok, val in items:
        bad += not ok
        out.append(f"| {sec} | {text} | {val} | {'✓' if ok else '✗ 需要复核结论'} |")
    out.append(f"\n{'全部成立。' if not bad else f'有 {bad} 条不成立：请修改对应结论，并在变更记录里写明。'}")
    return "\n".join(out), bad
blocks = {"cn_now": nb, "cn_trend": tb, "cn_index": ib, "cn_overall": ob, "cn_channels": chb, "cn_events": evb, "cn_size": szb, "cn_robust": rb}
RESULT = dict(ov=ov, ch=ch, base=base, evk=evk, eps=[(months[a], months[b]) for a, b in eps], cut_rate=cut_rate, sd=sd,
              last=months[-1], V={k: V[k] for k in ("A_price", "A_qty", "B_price", "B_qty")}, months=months)

kb, bad = checks()
blocks["cn_checks"] = kb

if __name__ == "__main__" and DOC != "-":
    doc = open(DOC, encoding="utf-8").read()
    for k, v in blocks.items():
        doc = fill(doc, k, v)
    open(DOC, "w", encoding="utf-8", newline="\n").write(doc)
    if PAGE:   # 分析报告页的图表数据：月度序列与美元收紧期
        keys = ["A_price", "A_qty", "B_price", "B_qty", "fr007", "dr007", "shibor3m", "cn10y", "us10y", "m2", "m1", "loan12",
                "rrr", "policy", "usdcny", "fxres", "spread", "real10y", "dxy", "dff"]
        rnd = lambda x, k: None if np.isnan(x) else round(float(x), 1 if k in ("fxres", "dxy") else 4)
        page = {"m": months, **{k: [rnd(x, k) for x in V[k]] for k in keys},
                "eps": [{"label": e.get("label"), "a": e["span"][0], "b": e["span"][1]} for e in evk]}
        json.dump(page, open(PAGE, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"ANALYSIS.md（B、C 部分）已更新，数据截至 {months[-1]}；结论复核：{'全部成立' if not bad else f'{bad} 条不成立，需要人工修改结论'}")
elif DOC == "-":   # 试算：把各区块写到第三个参数指定的文件
    open(PAGE, "w", encoding="utf-8").write("".join(f"\n===== {k}\n{v}\n" for k, v in blocks.items()))
