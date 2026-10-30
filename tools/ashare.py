# A 股成交额专题：成交额为什么腰斩？分解（价格 vs 换手率）、量价弹性、杠杆资金、宽基 ETF 申赎、IPO 募资、政策事件时间线、
# 宏观流动性；回填 docs/ashare/REPORT.md 的 <!-- AUTO:ash_* --> 区块并复核结论依赖的数据条件，输出报告页的图表数据。
# A-share turnover study: decomposition, volume-price elasticity, margin, broad-ETF flows, IPOs, policy timeline, macro liquidity.
# 用法 | usage: python -I ashare.py <raw 目录> <docs/ashare/REPORT.md> <输出 build/ashare.json>
import bisect, datetime, json, re, sys
import numpy as np

RAW, DOC, PAGE = sys.argv[1:4]
A = f"{RAW}/ashare"

# 政策与市场事件（人工整理，注明来源与可靠程度；新增事件只改这里）
EVENTS = [
    ("2025-07-07", "交易所《程序化交易管理实施细则》施行（高频交易认定、异常交易监控、差异化收费）", "政策",
     "[中国基金报](https://www.chnfund.com/article/AR471f2f67-bf20-715c-873d-3a190dfce52d)、[证券时报](https://www.stcn.com/article/detail/2445915.html)", "官方媒体报道"),
    ("2026-01-14", "监管\"降温\"组合措施：融资保证金比例由 80% 上调至 100%（日期为报道日）", "政策",
     "[央广财经](https://finance.cnr.cn/ycbd/20260114/t20260114_527493326.shtml)", "官方媒体报道"),
    ("2026-04-07", "《关于短线交易监管的若干规定》施行；另有自媒体称同时收紧高频交易认定标准（每秒 300 笔降至 15 笔）", "政策",
     "[东方财富财富号](https://caifuhao.eastmoney.com/news/20260403204102408912550)", "自媒体，未找到官方原文，高频标准的说法尤其存疑"),
    ("2026-06-17", "陆家嘴论坛前后监管表态：重点是净化市场生态、引导长线资金，没有短期刺激措施（日期为报道日）", "政策表态",
     "[新浪财经](https://finance.sina.com.cn/wm/2026-06-17/doc-inicsvwv3932627.shtml)", "财经媒体评论"),
    ("2026-07-10", "科技（TMT）板块成交额见顶（约 1.7 万亿元），此后 AI、算力等主线资金获利了结", "市场",
     "[界面新闻](https://m.jiemian.com/article/15186034.html)、[东方财富网](https://finance.eastmoney.com/a/202610143895341434.html)", "财经媒体统计"),
    ("2026-09-30", "国庆长假前交投收缩（季节性）", "季节性",
     "[新浪财经](https://finance.sina.com.cn/money/gzqh/futuresyspzx/2026-09-30/doc-initpxxr2410861.shtml)", "财经媒体报道"),
]

# ---------- 读数据 ----------
csi = {d: v for d, v in json.load(open(f"{A}/csi_all.json")).items() if d > "2019-01-01"}
days = sorted(csi)
T = np.array([csi[d]["amt"] for d in days], float)        # 日成交额，亿元
P = np.array([csi[d]["close"] for d in days], float)      # 中证全指
mg = {x["STATISTICS_DATE"][:10]: x for x in json.load(open(f"{A}/margin.json", encoding="utf-8"))}
mk = sorted(mg)
mget = lambda d, k: (lambda i: mg[mk[i]].get(k) if i >= 0 else None)(bisect.bisect_right(mk, d) - 1)
etf = json.load(open(f"{A}/etf_shares.json"))
etf_names = json.load(open(f"{A}/etf_list.json", encoding="utf-8"))
ipo = json.load(open(f"{A}/ipo.json", encoding="utf-8"))
repo = json.load(open(f"{RAW}/cn/repo.json"))
ms = {x["REPORT_DATE"][:7]: x for x in json.load(open(f"{RAW}/cn/money_supply.json", encoding="utf-8"))}
N = len(days)
idx = {d: i for i, d in enumerate(days)}

# 周度面板：每周最后一个交易日；成交额取周内日均
wk = lambda s: datetime.date.fromisoformat(s).isocalendar()[:2]
wend = [i for i in range(N) if i == N - 1 or wk(days[i]) != wk(days[i + 1])]
W = []
start = 0
for e in wend:
    s = start
    W.append(dict(d=days[e], amt=T[s:e + 1].mean(), close=P[e], closeavg=P[s:e + 1].mean()))
    start = e + 1
wd = [w["d"] for w in W]
WT = np.array([w["amt"] for w in W])
WP = np.array([w["closeavg"] for w in W])

# ---------- 阶段 ----------
mon_amt = {}
for d, a in zip(days, T):
    mon_amt.setdefault(d[:7], []).append(a)
mon_avg = {m: np.mean(v) for m, v in mon_amt.items()}
mlist = sorted(m for m in mon_avg if m >= "2024-01")
pair = max(range(len(mlist) - 1), key=lambda j: np.mean(mon_amt[mlist[j]] + mon_amt[mlist[j + 1]]))
PEAK = (mlist[pair], mlist[pair + 1])                     # 日均成交额最高的连续两个月
pk = [i for i, d in enumerate(days) if PEAK[0] <= d[:7] <= PEAK[1]]
rc = list(range(N - 20, N))                               # 最近 20 个交易日
ipk = int(np.argmax(np.where(np.array(days) >= "2025-01-01", P, -1)))   # 2025 年以来指数最高点
rally0 = int(np.argmin(np.where((np.array(days) >= (datetime.date.fromisoformat(days[ipk]) - datetime.timedelta(days=365)).isoformat())
                                & (np.arange(N) <= ipk), P, np.inf)))       # 最高点前一年内的最低点
mean = lambda arr, sel: float(np.mean([arr[i] for i in sel]))
M = lambda key, sel: float(np.mean([mget(days[i], key) for i in sel if mget(days[i], key) is not None]))
dr = lambda sel: float(np.mean([float(repo[days[i]]["FDR007"]) for i in sel if days[i] in repo and repo[days[i]].get("FDR007")]))


def etf_sum(d):
    k = [x for x in sorted(etf) if x <= d]
    return sum(etf[k[-1]].values()) / 1e4 if k else None     # 亿份


def ipo_month(m):
    sel = [x for x in ipo if x.get("APPLY_DATE") and x["APPLY_DATE"][:7] == m and x.get("NETSUMFINA")]
    # 北交所的净募资单位是元，其他板块是亿元（例如 15.44 表示 15.44 亿元），按数值大小区分
    return len(sel), sum(x["NETSUMFINA"] / 1e8 if x["NETSUMFINA"] > 1e5 else x["NETSUMFINA"] for x in sel)   # 只数，亿元


fmt = lambda v, d=0: f"{v:,.{d}f}"
pct = lambda a, b: (b / a - 1) * 100
R = {}

# ---------- 总览 ----------
def b_overview():
    t_pk, t_rc = mean(T, pk), mean(T, rc)
    p_pk, p_rc = mean(P, pk), mean(P, rc)
    rate = lambda sel: np.mean([T[i] / P[i] for i in sel])
    mt_pk, mt_rc = M("MARGIN_TRADE_AMT", pk), M("MARGIN_TRADE_AMT", rc)
    fb_pk, fb_rc = mget(days[pk[-1]], "FIN_BALANCE"), mget(days[-1], "FIN_BALANCE")
    per_month = lambda a, b: sum(v for d, v in FLOW.items() if a < d <= b) / max(1, (datetime.date.fromisoformat(b) - datetime.date.fromisoformat(a)).days / 30.44)
    e_pk, e_rc = per_month(days[pk[0] - 1], days[pk[-1]]), per_month(days[rc[0] - 1], days[-1])
    ipo_pk = [ipo_month(m) for m in PEAK]
    last_m = [m for m in sorted({d[:7] for d in days}) if m < days[-1][:7]][-2:]   # 最近两个完整月
    ipo_rc = [ipo_month(m) for m in last_m]
    m1 = lambda m: ms[m]["CURRENCY_SAME"] if m in ms else None
    R.update(t_pk=t_pk, t_rc=t_rc, p_pk=p_pk, p_rc=p_rc, mt_pk=mt_pk, mt_rc=mt_rc, fb_pk=fb_pk, fb_rc=fb_rc, e_pk=e_pk, e_rc=e_rc,
             dr_pk=dr(pk), dr_rc=dr(rc), rate_pk=rate(pk), rate_rc=rate(rc),
             ipo_pk=sum(x[1] for x in ipo_pk) / 2, ipo_rc=sum(x[1] for x in ipo_rc) / 2)
    rows = [("日均成交额（亿元）", t_pk, t_rc, 0), ("中证全指（期间均值）", p_pk, p_rc, 0), ("换手率代理：成交额 ÷ 指数", rate(pk), rate(rc), 3),
            ("日均两融交易额（亿元）", mt_pk, mt_rc, 0), ("两融交易额占成交额（%）", M("TRADE_AMT_RATIO", pk), M("TRADE_AMT_RATIO", rc), 2),
            ("融资余额（亿元，期末）", fb_pk, fb_rc, 0),
            ("IPO 月均净募资（亿元）", R["ipo_pk"], R["ipo_rc"], 0), ("DR007（%，期间均值）", R["dr_pk"], R["dr_rc"], 2)]
    out = [f"峰值阶段为日均成交额最高的连续两个月（{PEAK[0]} 至 {PEAK[1]}）；最近阶段为最近 20 个交易日（{days[rc[0]]} 至 {days[-1]}）。"
           f"IPO 的最近阶段取最近两个完整月（{last_m[0]}、{last_m[1]}）。\n",
           "| 指标 | 峰值阶段 | 最近阶段 | 变化 |", "|---|---|---|---|"]
    for name, a, b, dg in rows:
        out.append(f"| {name} | {fmt(a, dg)} | {fmt(b, dg)} | {pct(a, b):+.0f}% |")
    out.append(f"| 主要宽基 ETF 资金净流入（亿元，按月平均） | {e_pk:+,.0f} | {e_rc:+,.0f} | — |")
    m1s = [(m, m1(m)) for m in (PEAK[1], max(ms))]
    out.append(f"\nM1 同比：{m1s[0][0]} 为 {m1s[0][1]}%，{m1s[1][0]} 为 {m1s[1][1]}%。指数最高点在 {days[ipk]}（{P[ipk]:,.0f}），"
               f"此前一年内的最低点在 {days[rally0]}（{P[rally0]:,.0f}）。")
    return "\n".join(out)


# ---------- 分解 ----------
def b_decomp():
    lt = np.log(R["t_rc"] / R["t_pk"])
    lp = np.log(R["p_rc"] / R["p_pk"])
    lr = lt - lp
    R.update(share_price=lp / lt, share_rate=lr / lt)
    mt_share = (R["mt_pk"] - R["mt_rc"]) / (R["t_pk"] - R["t_rc"])
    R["mt_share"] = mt_share
    out = ["成交额 = 市值 × 换手率。用中证全指近似总市值的变化（忽略新股上市和股本变动），成交额的下降可以拆成两部分（按对数拆分，两部分相加等于总变化）：\n",
           "| 部分 | 对数变化 | 占总下降的比例 |", "|---|---|---|",
           f"| 成交额（合计） | {lt:+.3f}（{(np.exp(lt)-1)*100:+.0f}%） | 100% |",
           f"| 指数下跌带来的部分 | {lp:+.3f}（{(np.exp(lp)-1)*100:+.0f}%） | {lp/lt*100:.0f}% |",
           f"| 换手率下降带来的部分 | {lr:+.3f}（{(np.exp(lr)-1)*100:+.0f}%） | {lr/lt*100:.0f}% |",
           f"\n两融交易额（融资买入 + 融券卖出）从峰值阶段的日均 {fmt(R['mt_pk'])} 亿元降到 {fmt(R['mt_rc'])} 亿元，"
           f"占成交额下降的 **{mt_share*100:.0f}%**；其余 {100 - mt_share*100:.0f}% 来自非两融资金。"]
    return "\n".join(out)


# ---------- 量价弹性 ----------
def b_elastic():
    out, keep = [], {}
    x, y = np.log(WP), np.log(WT)
    for name, a in (("2019 年至今", "2019-01-01"), ("2024 年至今", "2024-01-01")):
        m = np.array([d >= a for d in wd])
        X = np.column_stack([np.ones(m.sum()), x[m]])
        b, *_ = np.linalg.lstsq(X, y[m], rcond=None)
        r2 = 1 - (y[m] - X @ b).var() / y[m].var()
        pred = (R["p_rc"] / R["p_pk"]) ** b[1] - 1
        keep[name] = (b[1], r2, pred)
    out.append("用周度数据回归 log(周日均成交额) = a + b × log(中证全指)，b 是\"量价弹性\"：指数涨跌 1%，成交额平均涨跌 b%。"
               "再用 b 推算：只看峰值阶段到最近阶段的指数跌幅，成交额\"应该\"跌多少。\n")
    out += ["| 样本 | 量价弹性 b | R² | 按指数跌幅推算的成交额变化 | 实际变化 |", "|---|---|---|---|---|"]
    for name, (b1, r2, pred) in keep.items():
        out.append(f"| {name} | {b1:.2f} | {r2*100:.0f}% | {pred*100:+.0f}% | {pct(R['t_pk'], R['t_rc']):+.0f}% |")
    # 周度领先滞后：指数周涨跌 与 成交额周变化
    ret = np.diff(np.log(np.array([w["close"] for w in W])))
    dT = np.diff(np.log(WT))
    sel = np.array([d >= "2024-01-01" for d in wd[1:]])
    r, dd = ret[sel], dT[sel]
    lag = {}
    for L in (-2, -1, 0, 1, 2):     # L > 0：指数涨跌领先成交额变化 L 周
        a_, b_ = (r[:-L], dd[L:]) if L > 0 else (r[-L:], dd[:L]) if L < 0 else (r, dd)
        lag[L] = np.corrcoef(a_, b_)[0, 1]
    out.append("\n2024 年以来，指数周涨跌幅与成交额周变化（对数）的相关系数：\n")
    out += ["| 成交额领先 2 周 | 成交额领先 1 周 | 同周 | 指数领先 1 周 | 指数领先 2 周 |", "|---|---|---|---|---|",
            "| " + " | ".join(f"{lag[L]:+.2f}" for L in (-2, -1, 0, 1, 2)) + " |"]
    R.update(elastic=keep, lag=lag)
    return "\n".join(out)


# ---------- 杠杆 ----------
def b_lev():
    fb = {d: mg[d]["FIN_BALANCE"] for d in mk if d >= "2024-01-01" and mg[d].get("FIN_BALANCE")}
    fk = sorted(fb)
    fpk = max(fk, key=lambda d: fb[d])
    # 成交额周度最高点
    wpk = wd[int(np.argmax(WT))]
    R.update(fb_peak=(fpk, fb[fpk]), fb_last=(fk[-1], fb[fk[-1]]), turnover_peak_week=wpk, index_peak=days[ipk])
    out = ["| 时点 | 日期 | 数值 |", "|---|---|---|",
           f"| 周日均成交额最高 | {wpk} 当周 | {fmt(WT.max())} 亿元 |",
           f"| 中证全指最高 | {days[ipk]} | {P[ipk]:,.0f} |",
           f"| 融资余额最高 | {fpk} | {fmt(fb[fpk])} 亿元 |",
           f"| 融资余额最新 | {fk[-1]} | {fmt(fb[fk[-1]])} 亿元（较最高 {pct(fb[fpk], fb[fk[-1]]):+.0f}%） |"]
    out.append("\n各月月末融资余额与当月日均两融交易额占成交额的比例：\n")
    out += ["| 月份 | 融资余额（亿元） | 两融交易额占比（%） | 日均成交额（亿元） |", "|---|---|---|---|"]
    for m in sorted({d[:7] for d in fk if d >= "2025-06"}):
        last = [d for d in fk if d[:7] == m][-1]
        ratios = [mg[d]["TRADE_AMT_RATIO"] for d in mk if d[:7] == m and mg[d].get("TRADE_AMT_RATIO")]
        out.append(f"| {m} | {fmt(fb[last])} | {np.mean(ratios):.2f} | {fmt(mon_avg.get(m, float('nan')))} |")
    return "\n".join(out)


# ---------- 宽基 ETF ----------
px = json.load(open(f"{A}/etf_price.json"))


def price_at(c, d):
    ks = sorted(px[c])
    i = bisect.bisect_right(ks, d) - 1
    return px[c][ks[max(i, 0)]]


def etf_flows():
    """每周资金净流入（亿元）= 份额变化（亿份）× 当周收盘价。份额单周变化超过约 35%、且前后一周内价格朝相反方向跳动超过约 35% 的，
    视为份额拆分或合并，不计入资金流"""
    ek = sorted(etf)
    flow = {d: 0.0 for d in ek[1:]}
    splits = []
    for c in etf_names:
        for i in range(1, len(ek)):
            a, b = etf[ek[i - 1]].get(c), etf[ek[i]].get(c)
            if not a or not b:
                continue
            ls = np.log(b / a)
            if abs(ls) > 0.3:
                rs = [np.log(price_at(c, ek[k]) / price_at(c, ek[k - 1])) for k in (i - 1, i, i + 1) if 1 <= k < len(ek)]
                if any(abs(r) > 0.3 and np.sign(r) != np.sign(ls) for r in rs):
                    splits.append((c, ek[i], (b / a - 1) * 100))
                    continue
            flow[ek[i]] += (b - a) / 1e4 * price_at(c, ek[i])
    return ek, flow, splits


EK, FLOW, SPLITS = etf_flows()
CUM = np.cumsum([FLOW[d] for d in EK[1:]])


def b_etf():
    sumflow = lambda a, b: sum(v for d, v in FLOW.items() if a < d <= b)
    seg = [("上涨阶段", days[rally0], days[ipk]), ("其中：2026 年 1 月", "2025-12-31", "2026-01-31"),
           ("下跌阶段", days[ipk], EK[-1]), ("其中：成交额见顶以后", R["turnover_peak_week"], EK[-1])]
    out = ["上交所 9 只主要宽基 ETF（上证50、上证180、沪深300 三只、中证500、中证1000、科创50 两只）的资金净流入：每周份额变化 × 当周收盘价。"
           "大额申赎通常被视为\"国家队\"等大资金的动向，但数据本身不能区分是谁在申赎；深交所上市的宽基 ETF 没有纳入。\n",
           "| 阶段 | 起止 | 资金净流入（亿元） |", "|---|---|---|"]
    keep = {}
    for name, a, b in seg:
        keep[name] = sumflow(a, b)
        out.append(f"| {name} | {a} → {b} | {keep[name]:+,.0f} |")
    R["etf_seg"] = keep
    wret = {w["d"]: (W[j]["close"] / W[j - 1]["close"] - 1) * 100 for j, w in enumerate(W) if j}
    out.append("\n按月的资金净流入（亿元）与当月日均成交额：\n")
    out += ["| 月份 | ETF 资金净流入（亿元） | 日均成交额（亿元） |", "|---|---|---|"]
    for m in sorted({d[:7] for d in EK if d >= "2025-06"}):
        out.append(f"| {m} | {sum(v for d, v in FLOW.items() if d[:7] == m):+,.0f} | {fmt(mon_avg.get(m, float('nan')))} |")
    ch = sorted(FLOW.items(), key=lambda x: x[1])
    out.append("\n2024 年以来单周资金进出最大的几次（周末日期；同周中证全指涨跌幅）：\n")
    out += ["| 方向 | 周 | 资金净流入（亿元） | 同周指数涨跌 |", "|---|---|---|---|"]
    for lab, lst in (("流入", ch[::-1][:5]), ("流出", ch[:5])):
        for d, v in lst:
            out.append(f"| {lab} | {d} | {v:+,.0f} | {wret.get(d, float('nan')):+.1f}% |")
    if SPLITS:
        out.append("\n识别为份额拆分或合并、没有计入资金流的：" + "；".join(f"{etf_names[c]}（{c}）{d} 当周份额 {v:+.0f}%" for c, d, v in SPLITS) + "。")
    return "\n".join(out)


# ---------- IPO ----------
def b_ipo():
    out = ["| 月份 | 发行只数 | 净募资（亿元） | 日均成交额（亿元） |", "|---|---|---|---|"]
    keep = {}
    for m in sorted({d[:7] for d in days if d >= "2025-01"}):
        n, amt = ipo_month(m)
        keep[m] = amt
        out.append(f"| {m} | {n} | {amt:,.0f} | {fmt(mon_avg[m])} |")
    out.append("\n按申购日期归月；净募资为发行公告中的募资净额。")
    R["ipo"] = keep
    return "\n".join(out)


# ---------- 事件 ----------
def b_events():
    out = ["每个事件前后 4 周的日均成交额与中证全指变化（事件日所在周不计入前后两侧）：\n",
           "| 日期 | 事件 | 类型 | 前 4 周日均成交额（亿元） | 后 4 周日均成交额（亿元） | 成交额变化 | 指数变化 | 来源 | 可靠程度 |",
           "|---|---|---|---|---|---|---|---|---|"]
    keep = []
    for d, desc, typ, src, rel in EVENTS:
        j = bisect.bisect_left(wd, d)
        if j < 4 or j + 4 >= len(W):
            after = "—"
        b4 = np.mean(WT[j - 4:j]) if j >= 4 else np.nan
        a4 = np.mean(WT[j + 1:j + 5]) if j + 5 <= len(W) else np.nan
        pb = np.mean([w["closeavg"] for w in W[j - 4:j]]) if j >= 4 else np.nan
        pa = np.mean([w["closeavg"] for w in W[j + 1:j + 5]]) if j + 5 <= len(W) else np.nan
        keep.append((d, b4, a4))
        out.append(f"| {d} | {desc} | {typ} | {fmt(b4)} | {'—' if np.isnan(a4) else fmt(a4)} | "
                   f"{'—' if np.isnan(a4) else f'{pct(b4, a4):+.0f}%'} | {'—' if np.isnan(pa) else f'{pct(pb, pa):+.1f}%'} | {src} | {rel} |")
    R["events"] = keep
    return "\n".join(out)


def b_macro():
    m1 = [(m, ms[m]["CURRENCY_SAME"], ms[m]["BASIC_CURRENCY_SAME"]) for m in sorted(ms) if m >= "2025-06"]
    out = ["| 月份 | DR007 月均（%） | M1 同比（%） | M2 同比（%） |", "|---|---|---|---|"]
    for m, a, b in m1:
        sel = [i for i, d in enumerate(days) if d[:7] == m]
        out.append(f"| {m} | {dr(sel):.2f} | {a} | {b} |")
    return "\n".join(out)


def b_checks():
    el = R["elastic"]["2019 年至今"]
    items = [
        ("发现 1", "成交额较峰值阶段下降超过 40%", pct(R["t_pk"], R["t_rc"]) <= -40, f"{pct(R['t_pk'], R['t_rc']):+.0f}%"),
        ("发现 1", "换手率下降对成交额下降的贡献大于指数下跌的贡献", R["share_rate"] > R["share_price"],
         f"换手率 {R['share_rate']*100:.0f}% / 指数 {R['share_price']*100:.0f}%"),
        ("发现 2", "按 2019 年以来的量价弹性，指数跌幅可以解释成交额下降的六成以上（按对数）", np.log(1 + el[2]) / np.log(R["t_rc"] / R["t_pk"]) >= 0.6,
         f"推算 {el[2]*100:+.0f}% / 实际 {pct(R['t_pk'], R['t_rc']):+.0f}%，解释 {np.log(1 + el[2]) / np.log(R['t_rc'] / R['t_pk'])*100:.0f}%"),
        ("发现 2", "同周量价正相关明显（相关系数 > 0.3）", R["lag"][0] > 0.3, f"{R['lag'][0]:+.2f}"),
        ("发现 3", "融资余额最高点不晚于成交额周度最高点后 8 周，即杠杆退潮和缩量基本同步",
         (datetime.date.fromisoformat(R["fb_peak"][0]) - datetime.date.fromisoformat(R["turnover_peak_week"])).days <= 56,
         f"融资余额最高 {R['fb_peak'][0]}，成交额最高 {R['turnover_peak_week']} 当周"),
        ("发现 3", "两融交易额的下降只占成交额下降的一小部分（低于 25%）", R["mt_share"] < 0.25, f"{R['mt_share']*100:.0f}%"),
        ("发现 4", "成交额见顶以后主要宽基 ETF 为资金净流入，即大资金没有通过宽基 ETF 撤出", R["etf_seg"]["其中：成交额见顶以后"] > 0,
         f"{R['etf_seg']['其中：成交额见顶以后']:+,.0f} 亿元"),
        ("发现 4", "上涨阶段主要宽基 ETF 合计净流出超过 5,000 亿元", R["etf_seg"]["上涨阶段"] < -5000, f"{R['etf_seg']['上涨阶段']:+,.0f} 亿元"),
        ("发现 4", "2026 年 1 月主要宽基 ETF 资金净流出超过 1,000 亿元，即上涨期有大资金减持降温", R["etf_seg"]["其中：2026 年 1 月"] < -1000,
         f"{R['etf_seg']['其中：2026 年 1 月']:+,.0f} 亿元"),
        ("发现 5", "最近阶段的 IPO 月均募资没有比峰值阶段明显增加（增幅不超过 50%）", R["ipo_rc"] <= R["ipo_pk"] * 1.5,
         f"{fmt(R['ipo_pk'])} → {fmt(R['ipo_rc'])} 亿元"),
        ("发现 5", "DR007 没有上升（最近阶段不高于峰值阶段 + 0.1 个百分点）", R["dr_rc"] <= R["dr_pk"] + 0.1, f"{R['dr_pk']:.2f}% → {R['dr_rc']:.2f}%"),
    ]
    out = ["| 对应 | 依赖的数据条件 | 当前数值 | 状态 |", "|---|---|---|---|"]
    bad = 0
    for sec, text, ok, val in items:
        bad += not ok
        out.append(f"| {sec} | {text} | {val} | {'✓' if ok else '✗ 需要复核结论'} |")
    out.append(f"\n{'全部成立。' if not bad else f'有 {bad} 条不成立：请修改对应结论，并在变更记录里写明。'}")
    return "\n".join(out), bad


def fill(doc, name, body):
    pat = re.compile(rf"(<!-- AUTO:{name} -->\n).*?(<!-- /AUTO:{name} -->)", re.S)
    if not pat.search(doc):
        sys.exit(f"REPORT.md 里缺少 AUTO:{name} 标记")
    return pat.sub(lambda m: m.group(1) + "\n" + body.strip("\n") + "\n\n" + m.group(2), doc)


blocks = {"ash_overview": b_overview(), "ash_decomp": b_decomp(), "ash_elastic": b_elastic(), "ash_lev": b_lev(), "ash_etf": b_etf(),
          "ash_ipo": b_ipo(), "ash_events": b_events(), "ash_macro": b_macro()}
kb, bad = b_checks()
blocks["ash_checks"] = kb
blocks["ash_updated"] = f"数据截至 {days[-1]}，由 `tools/update.sh` 于 {datetime.date.today()} 生成。"

if DOC == "-":       # 试算：各区块写到 PAGE 指定的文件
    open(PAGE, "w", encoding="utf-8").write("".join(f"\n===== {k}\n{v}\n" for k, v in blocks.items()))
else:
    doc = open(DOC, encoding="utf-8").read()
    for k, v in blocks.items():
        doc = fill(doc, k, v)
    open(DOC, "w", encoding="utf-8", newline="\n").write(doc)
    # 报告页图表数据：2024 年起的周度序列
    sel = [j for j, d in enumerate(wd) if d >= "2024-01-01"]
    ek = sorted(etf)
    ipo_m = {m: ipo_month(m)[1] for m in sorted({wd[j][:7] for j in sel})}
    page = {"d": [wd[j] for j in sel], "amt": [round(float(WT[j])) for j in sel], "close": [round(W[j]["close"], 1) for j in sel],
            "fin": [round(mget(wd[j], "FIN_BALANCE") or 0) for j in sel],
            "mtr": [round(float(np.mean([mg[d]["TRADE_AMT_RATIO"] for d in mk if wk(d) == wk(wd[j]) and mg[d].get("TRADE_AMT_RATIO")] or [np.nan])), 2) for j in sel],
            "etf": [round(float(CUM[bisect.bisect_right(EK[1:], wd[j]) - 1]), 0) if bisect.bisect_right(EK[1:], wd[j]) else 0 for j in sel],
            "ipo": [round(ipo_m[wd[j][:7]], 1) for j in sel],
            "events": [{"d": d, "t": re.sub(r"（[^）]*）", "", desc)[:34], "type": typ} for d, desc, typ, _, _ in EVENTS],
            "peak": list(PEAK), "recent": [days[rc[0]], days[-1]]}
    page["mtr"] = [None if (isinstance(x, float) and np.isnan(x)) else x for x in page["mtr"]]
    json.dump(page, open(PAGE, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"A 股成交额专题：REPORT.md 已更新，数据截至 {days[-1]}；结论复核：{'全部成立' if not bad else f'{bad} 条不成立，需要人工修改结论'}")
