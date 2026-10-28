# 专题验证 2：红利指数按 MA120 均线定投 / 止盈。回测图片中的规则并与普通定投对比，回填 docs/VERIFY.md 中验证 2 的
# AUTO 区块、复核结论依赖的数据条件，并输出页面用的数据 build/verify2.json（按周抽样的价格与偏离度、预先算好的回测结果）。
# Verification 2: backtest the dividend-index MA120 DCA / take-profit rule vs plain DCA; refill VERIFY.md and emit page data.
# 用法 | usage: python -I verify2.py <raw 目录> <docs/VERIFY.md> <输出 build/verify2.json>
import bisect, datetime, json, re, sys

RAW, DOC, PAGE = sys.argv[1:4]
INDEXES = [("中证红利", "000922", "H00922"), ("红利低波", "H30269", "H20269"), ("红利低波100", "930955", "H20955"),
           ("央企红利", "000825", "H00825"), ("国企红利", "000824", "H00824"), ("上证红利", "000015", "H00015"),
           ("港股通高股息", "930914", "H20914")]
HK = "港股通高股息"
MODES = {"daily": "120 日均线", "weekly": "120 周均线"}
# 规则的具体化：pause 高于均线时暂停定投；s1 / s2 偏离 > 10% / > 20% 时卖出持仓的比例；add 偏离 < −20% 时投入现金的比例；
# refill 回到均线下方的定投日再投入现金的方式（none 只投当月 1 份 / gradual 另加现金的 1/12 / all 现金全部投入）
VARIANTS = {
    "字面版": dict(pause=True, s1=0.3, s2=1.0, add=0.5, refill="none"),
    "字面版+一次买回": dict(pause=True, s1=0.3, s2=1.0, add=0.5, refill="all"),
    "只停投": dict(pause=True, s1=0, s2=0, add=0.5, refill="all"),
    "只止盈": dict(pause=False, s1=0.3, s2=1.0, add=0.5, refill="all"),
    "温和版": dict(pause=True, s1=0.2, s2=0.5, add=0.5, refill="gradual"),
}
REFILL = {"none": 0, "gradual": 1 / 12, "all": 1}
THRESH = [0.08, 0.10, 0.12, 0.15, 0.20]


def load(code):
    d = json.loads(open(f"{RAW}/{code}.json", "rb").read().decode("utf-8"))["data"]
    return {f"{x['tradeDate'][:4]}-{x['tradeDate'][4:6]}-{x['tradeDate'][6:]}": x["close"]
            for x in d if x["close"] and x["tradeDate"] > "20040101"}


MM = load("H11025")
mmk = sorted(MM)
mm_at = lambda d: MM[mmk[max(0, bisect.bisect_right(mmk, d) - 1)]]


def deviation(days, P, mode):
    """偏离度 = 价格 / 均线 − 1。daily：120 个交易日均线；weekly：120 周均线（只用已经结束的周）"""
    dev = [None] * len(days)
    if mode == "daily":
        s = 0.0
        for i, p in enumerate(P):
            s += p
            if i >= 120:
                s -= P[i - 120]
            if i >= 119:
                dev[i] = p / (s / 120) - 1
        return dev
    wk = lambda d: datetime.date.fromisoformat(d).isocalendar()[:2]
    wclose = [(i, P[i]) for i, d in enumerate(days) if i == len(days) - 1 or wk(d) != wk(days[i + 1])]
    cs = [0.0]
    for _, c in wclose:
        cs.append(cs[-1] + c)
    j = 0
    for i in range(len(days)):
        while j < len(wclose) and wclose[j][0] < i:
            j += 1
        if j >= 120:
            dev[i] = P[i] / ((cs[j] - cs[j - 120]) / 120) - 1
    return dev


def xirr(flows):
    t0 = datetime.date.fromisoformat(flows[0][0])
    ts = [((datetime.date.fromisoformat(d) - t0).days / 365.25, a) for d, a in flows]
    f = lambda r: sum(a / (1 + r) ** t for t, a in ts)
    lo, hi = -0.99, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if f(mid) > 0:
            lo = mid
        else:
            hi = mid
    return mid


def run(days, T, dev, i0, i1, v=None, k=1.0):
    """v=None 为普通定投。k 为阈值缩放（卖出线 10%·k / 20%·k，加仓线 −20%·k）。返回 (年化 XIRR, 平均股票仓位)"""
    units = cash = 0.0
    flows, armed_s1, armed_s2, armed_add = [], True, True, True
    month, eq_sum = None, 0.0
    for i in range(i0, i1 + 1):
        d = days[i]
        if i > i0:
            cash *= mm_at(d) / mm_at(days[i - 1])
        x = dev[i - 1] if i > 0 else None              # 用前一天的偏离度决策，当天收盘成交
        if x is not None:
            x /= k
        if d[:7] != month:                              # 每月第一个交易日：投入 1 份
            month = d[:7]
            flows.append((d, -1.0))
            cash += 1.0
            below = x is not None and x <= 0
            if v is None or not v["pause"] or below:
                amt = min(cash, 1.0 + ((cash - 1.0) * REFILL[v["refill"]] if v and below else 0))
                units += amt / T[i]
                cash -= amt
        if v and x is not None:
            if x <= 0:
                armed_s1 = armed_s2 = True
            if x >= 0:
                armed_add = True
            if x > 0.10 and armed_s1 and units > 0 and v["s1"]:
                cash += units * v["s1"] * T[i]; units *= 1 - v["s1"]; armed_s1 = False
            if x > 0.20 and armed_s2 and units > 0 and v["s2"]:
                cash += units * v["s2"] * T[i]; units *= 1 - v["s2"]; armed_s2 = False
            if x < -0.20 and armed_add and cash > 0 and v["add"]:
                amt = cash * v["add"]; units += amt / T[i]; cash -= amt; armed_add = False
        val = units * T[i] + cash
        eq_sum += units * T[i] / val if val else 0
    val = units * T[i1] + cash
    flows.append((days[i1], val))
    return xirr(flows), eq_sum / (i1 - i0 + 1)


med = lambda w: sorted(w)[len(w) // 2]
winp = lambda w: sum(x > 0 for x in w) / len(w) * 100

# ---------- 计算 ----------
R = {}          # R[name][mode] = dict(...)
DATA = {}
for name, pc, tc in INDEXES:
    Pm, Tm = load(pc), load(tc)
    days = sorted(set(Pm) & set(Tm))
    P, T = [Pm[d] for d in days], [Tm[d] for d in days]
    DATA[name] = (days, P, T)
    R[name] = {}
    for mode in MODES:
        dev = deviation(days, P, mode)
        valid = [x for x in dev if x is not None]
        st = next(i for i, x in enumerate(dev) if x is not None) + 1
        fr = lambda c: sum(1 for x in valid if c(x)) / len(valid) * 100
        full = {"定投": run(days, T, dev, st, len(days) - 1)}
        full.update({kk: run(days, T, dev, st, len(days) - 1, v) for kk, v in VARIANTS.items()})
        wins = {kk: [] for kk in VARIANTS}
        by_year, thr = {}, {t: [] for t in THRESH}
        for s in [i for i in range(st, len(days)) if i == st or days[i][:7] != days[i - 1][:7]]:
            end_d = (datetime.date.fromisoformat(days[s]) + datetime.timedelta(days=round(5 * 365.25))).isoformat()
            if end_d > days[-1]:
                continue
            e = bisect.bisect_right(days, end_d) - 1
            base = run(days, T, dev, s, e)[0]
            for kk, v in VARIANTS.items():
                wins[kk].append(run(days, T, dev, s, e, v)[0] - base)
            by_year.setdefault(days[s][:4], []).append(wins["字面版+一次买回"][-1])
            if mode == "weekly":
                for t in THRESH:
                    thr[t].append(run(days, T, dev, s, e, VARIANTS["字面版+一次买回"], t / 0.10)[0] - base)
        R[name][mode] = dict(dev=dev, start=days[st], cur=dev[-1], last=days[-1], full=full, wins=wins, by_year=by_year, thr=thr,
                             freq=(fr(lambda x: x > 0), fr(lambda x: x > 0.10), fr(lambda x: x > 0.20), fr(lambda x: x < -0.20)))

ASHARE = [n for n, _, _ in INDEXES if n != HK]


def zone(x):
    return ("偏离超过 +20%：大量卖出甚至清仓" if x > 0.20 else "偏离超过 +10%：卖出一部分" if x > 0.10 else
            "高于均线：停止定投" if x > 0 else "低于均线超过 20%：大量加仓" if x < -0.20 else "低于或持平均线：继续定投")


# ---------- 文档区块 ----------
def b_status():
    out = ["| 指数 | 数据截至 | 120 日均线：偏离 / 所处区间 | 120 周均线：偏离 / 所处区间 |", "|---|---|---|---|"]
    for n, _, _ in INDEXES:
        d, w = R[n]["daily"], R[n]["weekly"]
        out.append(f"| {n} | {d['last']} | {d['cur']*100:+.1f}%：{zone(d['cur'])} | {w['cur']*100:+.1f}%：{zone(w['cur'])} |")
    return "\n".join(out)


def b_freq():
    out = ["| 指数 | 均线 | 回测起点 | 高于均线 | 高 10% 以上 | 高 20% 以上 | 低 20% 以上 |", "|---|---|---|---|---|---|---|"]
    for mode, mt in MODES.items():
        for n, _, _ in INDEXES:
            r = R[n][mode]
            out.append(f"| {n} | {mt} | {r['start']} | " + " | ".join(f"{x:.1f}%" for x in r["freq"]) + " |")
    out.append("\n表中百分比为历史上处于该区间的交易日占比。")
    return "\n".join(out)


def b_full():
    out = []
    for mode, mt in MODES.items():
        out.append(f"\n**{mt}**：全期年化（XIRR），括号内为平均股票仓位\n")
        out.append("| 指数 | 普通定投 | " + " | ".join(VARIANTS) + " |")
        out.append("|---|---|" + "---|" * len(VARIANTS))
        for n, _, _ in INDEXES:
            f = R[n][mode]["full"]
            out.append(f"| {n} | {f['定投'][0]*100:.2f}% | " + " | ".join(f"{f[k][0]*100:.2f}%（{f[k][1]*100:.0f}%）" for k in VARIANTS) + " |")
    return "\n".join(out)


def b_windows():
    out = []
    for mode, mt in MODES.items():
        out.append(f"\n**{mt}**：5 年滚动窗口里跑赢普通定投的比例 / 年化差中位数（百分点）\n")
        out.append("| 指数 | 窗口数 | " + " | ".join(VARIANTS) + " |")
        out.append("|---|---|" + "---|" * len(VARIANTS))
        agg = {k: [] for k in VARIANTS}
        for n, _, _ in INDEXES:
            w = R[n][mode]["wins"]
            for k in VARIANTS:
                if n != HK:
                    agg[k] += w[k]
            out.append(f"| {n} | {len(w['字面版'])} | " + " | ".join(f"{winp(w[k]):.0f}% / {med(w[k])*100:+.2f}" for k in VARIANTS) + " |")
        out.append(f"| A 股红利合计（6 个） | {len(agg['字面版'])} | " + " | ".join(f"{winp(a):.0f}% / {med(a)*100:+.2f}" for a in agg.values()) + " |")
    return "\n".join(out)


def b_years():
    out = ["| 起点年份 | A 股红利（6 个）：窗口数 / 跑赢比例 / 中位差 | 港股通高股息：窗口数 / 跑赢比例 / 中位差 |", "|---|---|---|"]
    years = sorted({y for n, _, _ in INDEXES for y in R[n]["weekly"]["by_year"]})
    keep = {}
    for y in years:
        a = [x for n in ASHARE for x in R[n]["weekly"]["by_year"].get(y, [])]
        h = R[HK]["weekly"]["by_year"].get(y, [])
        keep[y] = a
        cell = lambda w: f"{len(w)} / {winp(w):.0f}% / {med(w)*100:+.2f}" if w else "—"
        out.append(f"| {y} | {cell(a)} | {cell(h)} |")
    return "\n".join(out), keep


def b_thresh():
    out = ["| 卖出线 / 清仓线 / 加仓线 | A 股红利（6 个）：跑赢比例 / 中位差 | 港股通高股息：跑赢比例 / 中位差 |", "|---|---|---|"]
    keep = {}
    for t in THRESH:
        a = [x for n in ASHARE for x in R[n]["weekly"]["thr"][t]]
        h = R[HK]["weekly"]["thr"][t]
        keep[t] = a
        out.append(f"| +{t*100:.0f}% / +{t*200:.0f}% / −{t*200:.0f}% | {winp(a):.0f}% / {med(a)*100:+.2f} | {winp(h):.0f}% / {med(h)*100:+.2f} |")
    return "\n".join(out), keep


def b_checks(years, thr):
    lit = [(n, m) for n, _, _ in INDEXES for m in MODES]
    a_day = [x for n in ASHARE for x in R[n]["daily"]["wins"]["字面版+一次买回"]]
    a_wk = [x for n in ASHARE for x in R[n]["weekly"]["wins"]["字面版+一次买回"]]
    bad_years = [x for y in ("2010", "2011", "2012") for x in years.get(y, [])]
    hk = R[HK]["weekly"]["full"]
    items = [
        ("结论 1", "字面版在两种均线、全部 7 个指数上的全期年化都低于普通定投",
         all(R[n][m]["full"]["字面版"][0] < R[n][m]["full"]["定投"][0] for n, m in lit), "—"),
        ("结论 1", "字面版的平均股票仓位都低于 40%", all(R[n][m]["full"]["字面版"][1] < 0.40 for n, m in lit),
         f"最高 {max(R[n][m]['full']['字面版'][1] for n, m in lit)*100:.0f}%"),
        ("结论 2", "120 日均线下，字面版+一次买回在 A 股红利上没有稳定优势（跑赢比例低于 60%，中位差绝对值小于 1 个百分点）",
         winp(a_day) < 60 and abs(med(a_day)) < 0.01, f"{winp(a_day):.0f}% / {med(a_day)*100:+.2f}"),
        ("结论 3", "120 周均线下，字面版+一次买回在 A 股红利上跑赢比例不低于 60%，中位差为正", winp(a_wk) >= 60 and med(a_wk) > 0,
         f"{winp(a_wk):.0f}% / {med(a_wk)*100:+.2f}"),
        ("结论 3", "阈值在 8%–20% 之间变化时，A 股红利的跑赢比例都不低于 60%", all(winp(w) >= 60 for w in thr.values()),
         f"最低 {min(winp(w) for w in thr.values()):.0f}%"),
        ("结论 4", "A 股红利起点在 2010–2012 年的 5 年窗口，跑赢比例低于 30%", winp(bad_years) < 30, f"{winp(bad_years):.0f}%"),
        ("结论 4", "港股通高股息在 120 周均线下，字面版+一次买回的全期年化低于普通定投", hk["字面版+一次买回"][0] < hk["定投"][0],
         f"{hk['字面版+一次买回'][0]*100:.2f}% 对 {hk['定投'][0]*100:.2f}%"),
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
        sys.exit(f"VERIFY.md 里缺少 AUTO:{name} 标记")
    return pat.sub(lambda m: m.group(1) + "\n" + body.strip("\n") + "\n\n" + m.group(2), doc)


yb, years = b_years()
tb, thr = b_thresh()
kb, bad = b_checks(years, thr)
doc = open(DOC, encoding="utf-8").read()
for name, body in (("v2_status", b_status()), ("v2_freq", b_freq()), ("v2_full", b_full()), ("v2_windows", b_windows()),
                   ("v2_years", yb), ("v2_thresh", tb), ("v2_checks", kb)):
    doc = fill(doc, name, body)
open(DOC, "w", encoding="utf-8", newline="\n").write(doc)

# ---------- 页面数据：共用周日期轴（每周最后一个交易日），各指数按日期对齐 ----------
ref = DATA["中证红利"][0]
wk = lambda d: datetime.date.fromisoformat(d).isocalendar()[:2]
wd = [d for i, d in enumerate(ref) if i == len(ref) - 1 or wk(d) != wk(ref[i + 1])]
page = {"d": wd, "idx": [], "modes": MODES, "variants": list(VARIANTS)}
for n, pc, tc in INDEXES:
    days, P, _ = DATA[n]
    item = {"name": n, "code": pc, "p": [], "dd": [], "dw": [], "res": {}}
    for d in wd:
        i = bisect.bisect_right(days, d) - 1
        ok = i >= 0 and days[0] <= d
        item["p"].append(round(P[i], 2) if ok else None)
        for key, mode in (("dd", "daily"), ("dw", "weekly")):
            x = R[n][mode]["dev"][i] if ok else None
            item[key].append(None if x is None else round(x, 4))
    for mode in MODES:
        r = R[n][mode]
        item["res"][mode] = {"start": r["start"], "定投": [round(r["full"]["定投"][0], 4), 1.0]}
        for k in VARIANTS:
            item["res"][mode][k] = [round(r["full"][k][0], 4), round(r["full"][k][1], 3), round(winp(r["wins"][k]), 1), round(med(r["wins"][k]), 4)]
    page["idx"].append(item)
json.dump(page, open(PAGE, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print(f"验证 2：VERIFY.md 已更新；结论复核：{'全部成立' if not bad else f'{bad} 条不成立，需要人工修改结论'}")
