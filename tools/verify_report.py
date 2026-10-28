# 专题验证的计算与文档回填：计算 docs/VERIFY.md 里所有数字，回填到 <!-- AUTO:名称 --> 标记之间，并复核结论依赖的数据条件。
# 验证 1：沪深300全收益跌破二级债基指数 = 底部？（用日度数据；页面用的是周度数据，日期可能差几天）
# Compute every number in docs/VERIFY.md from daily data, refill AUTO blocks, and re-check the conditions behind each conclusion.
# 用法 | usage: python -I verify_report.py <raw 目录> <build/bondfund.json> <docs/VERIFY.md>
import bisect, datetime, json, re, sys

RAW, BF, DOC = sys.argv[1:4]

# 万得 885007 公开的年度收益（%），用来校验复刻指数。来源见 VERIFY.md
W885007 = {2020: 9.12, 2021: 7.82, 2022: -5.07, 2023: 0.57, 2024: 4.90}
# 公认的阶段性大底（沪深300），用来看比值在底部时的位置
BOTTOMS = ["2008-11-04", "2012-12-03", "2014-03-20", "2016-01-28", "2019-01-03", "2020-03-19", "2022-10-31", "2024-02-02"]
BASES = [f"{y}-12-31" for y in range(2004, 2022)]
H = {"6 个月": 122, "1 年": 244, "2 年": 488, "3 年": 732}

csi = json.loads(open(f"{RAW}/H00300.json", "rb").read().decode("utf-8"))["data"]
eq = {f"{x['tradeDate'][:4]}-{x['tradeDate'][4:6]}-{x['tradeDate'][6:]}": x["close"] for x in csi if x["close"]}
rep = json.load(open(BF))
bf, nf = rep["level"], rep["n"]
bk = sorted(bf)
days = [d for d in sorted(eq) if d >= "2004-12-31" and d <= bk[-1]]
N = len(days)


def bf_at(d):
    return bf[bk[bisect.bisect_right(bk, d) - 1]]


E = [eq[d] for d in days]
B = [bf_at(d) for d in days]
fwd = lambda i, n: E[i + n] / E[i] - 1 if i + n < N else None
pc = lambda x: "—" if x is None else f"{x*100:+.1f}%"
idx_of = lambda d: next(i for i, x in enumerate(days) if x >= d)


def ratio(base):
    b0 = idx_of(base)
    return b0, [None] * b0 + [(E[i] / E[b0]) / (B[i] / B[b0]) for i in range(b0, N)]


def crossings(base):
    """在比值 ≥ 1 停留 60 个交易日以上后、第一次跌到 1 以下的日子"""
    b0, R = ratio(base)
    ev, run = [], 0
    for i in range(b0 + 1, N):
        if R[i] >= 1:
            run += 1
        else:
            if R[i - 1] >= 1 and run >= 60:
                ev.append(i)
            run = 0
    out = []
    for i in ev:
        lo = min(range(i, min(N, i + 732)), key=lambda j: E[j])
        out.append(dict(i=i, d=days[i], dd=E[lo] / E[i] - 1, lo=days[lo], wait=lo - i, **{k: fwd(i, n) for k, n in H.items()}))
    return out, R


def last_on(series, keys, d):
    return series[keys[bisect.bisect_right(keys, d) - 1]]


# ---------- 复刻指数校验 ----------
def replica_block():
    out = ["| 年份 | 复刻指数 | 万得 885007（公开） | 差距（百分点） |", "|---|---|---|---|"]
    gaps = []
    for y, v in W885007.items():
        r = (last_on(bf, bk, f"{y}-12-31") / last_on(bf, bk, f"{y-1}-12-31") - 1) * 100
        gaps.append(abs(r - v))
        out.append(f"| {y} | {r:+.2f}% | {v:+.2f}% | {r-v:+.2f} |")
    cnt = " ，".join(f"{y} 年 {nf[last_k]} 只" for y in (2005, 2008, 2012, 2016, 2020, 2024)
                     for last_k in [max(k for k in bk if k[:4] == str(y))])
    out.append(f"\n纳入基金数（年末）：{cnt}，最新 {nf[bk[-1]]} 只。剔除异常数据 {rep.get('dropped', 0)} 条。")
    return "\n".join(out), max(gaps)


# ---------- 基准 2004-12-31 ----------
def settled(R, start, need=60):
    """比值第一次在 1 以上连续停留 need 个交易日的那一天（站稳）"""
    run = 0
    for i in range(start, N):
        run = run + 1 if R[i] >= 1 else 0
        if run >= need:
            return i
    return None


def base_block():
    ev, R = crossings("2004-12-31")
    s = settled(R, 0)
    first_below = next((i for i in range(N) if R[i] < 1), None)
    imin = min(range(s, N), key=lambda i: R[i])
    i07 = min((i for i in range(N) if days[i] >= "2007-01-01"), key=lambda i: R[i])
    out = [f"- 起点之后沪深300先跌了一段，比值从 {days[first_below]} 起低于 1；{days[s]} 在 1 以上站稳（连续 60 个交易日）。",
           f"- 站稳之后的跌破次数：**{len(ev)}**。",
           f"- 站稳之后比值的最低点：**{R[imin]:.2f}**（{days[imin]}）；2007 年以后的最低点：**{R[i07]:.2f}**（{days[i07]}）。",
           f"- 最新比值：**{R[-1]:.2f}**（{days[-1]}）。", ""]
    out.append("| 条件 | 天数 | " + " | ".join(f"之后 {k}：平均收益 / 上涨概率" for k in H) + " |")
    out.append("|---|---|" + "---|" * len(H))
    for name, sel in (("全部交易日", range(N)), ("比值 < 1（跌破状态）", [i for i in range(N) if R[i] < 1]),
                      ("比值 ≥ 1", [i for i in range(N) if R[i] >= 1])):
        sel = list(sel)
        cells = []
        for n in H.values():
            f = [fwd(i, n) for i in sel if fwd(i, n) is not None]
            cells.append(f"{sum(f)/len(f)*100:+.1f}% / {sum(x > 0 for x in f)/len(f)*100:.0f}%" if f else "—")
        out.append(f"| {name} | {len(sel)} | " + " | ".join(cells) + " |")
    out.append("\n比值 < 1 的日子全部在起点之后、站稳之前这一段（2005 年到 2006 年年中），之后的远期收益很高，但这只是 2005–2007 年一段行情。")
    return "\n".join(out), len(ev), R[imin], days[imin], R[i07], days[i07]


# ---------- 换基准日 ----------
def sens_block():
    out = ["| 基准日 | 跌破次数 | 跌破日（之后 3 年内继续下跌幅度，距最低点交易日数） | 最新比值 |", "|---|---|---|---|"]
    all_dd = []
    for b in BASES:
        ev, R = crossings(b)
        all_dd += [e["dd"] for e in ev if e["i"] + 244 < N]          # 只统计之后至少有 1 年数据的跌破
        out.append(f"| {b} | {len(ev)} | " + "；".join(f"{e['d']}（{e['dd']*100:.0f}%，{e['wait']}）" for e in ev) + f" | {R[-1]:.2f} |")
    avg = sum(all_dd) / len(all_dd) if all_dd else 0
    out.append(f"\n所有基准日合计 {len(all_dd)} 次跌破（之后至少有 1 年数据的），跌破后 3 年内平均还要再跌 **{avg*100:.1f}%**，"
               f"其中再跌超过 10% 的有 {sum(x <= -0.10 for x in all_dd)} 次。")
    ev, _ = crossings("2014-12-31")
    out.append("\n以 2014-12-31 为基准的明细：\n")
    out.append("| 跌破日 | 之后 3 年内继续下跌 | 最低点日期 | 距最低点（交易日） | " + " | ".join(f"之后 {k}" for k in H) + " |")
    out.append("|---|---|---|---|" + "---|" * len(H))
    for e in ev:
        out.append(f"| {e['d']} | {e['dd']*100:.1f}% | {e['lo']} | {e['wait']} | " + " | ".join(pc(e[k]) for k in H) + " |")
    return "\n".join(out), avg


# ---------- 大底时的比值 ----------
def bottoms_block():
    _, R = ratio("2004-12-31")
    post = sorted(R[i] for i in range(N) if days[i] >= "2006-01-01")
    out = ["| 阶段底部 | 当天比值（基准 2004-12-31） | 在 2006 年以来的历史分位 |", "|---|---|---|"]
    pcts = {}
    for b in BOTTOMS:
        i = idx_of(b)
        p = sum(v <= R[i] for v in post) / len(post) * 100
        pcts[b] = p
        out.append(f"| {days[i]} | {R[i]:.2f} | {p:.0f}% |")
    return "\n".join(out), pcts


# ---------- 滚动 5 年分位（无前视） ----------
def rolling_block():
    W = 1220
    R = [e / b for e, b in zip(E, B)]
    out, keep = [], {}
    for q in (0.05, 0.10):
        sig = [False] * N
        for i in range(W, N):
            win = R[i - W:i + 1]
            sig[i] = sum(v <= R[i] for v in win) / len(win) <= q
        ev, gap = [], 999
        for i in range(W, N):
            if sig[i] and gap >= 120:
                ev.append(i)
            gap = 0 if sig[i] else gap + 1
        keep[q] = (sig, ev)
        out.append(f"\n**比值处在过去 5 年最低 {int(q*100)}% 区间**：首次信号 {len(ev)} 次，信号日共 {sum(sig)} 天。\n")
        out.append("| 首次信号日 | 之后 3 年内继续下跌 | 最低点日期 | " + " | ".join(f"之后 {k}" for k in H) + " |")
        out.append("|---|---|---|" + "---|" * len(H))
        for i in ev:
            lo = min(range(i, min(N, i + 732)), key=lambda j: E[j])
            out.append(f"| {days[i]} | {(E[lo]/E[i]-1)*100:.1f}% | {days[lo]} | " + " | ".join(pc(fwd(i, n)) for n in H.values()) + " |")
        cells = []
        for name, sel in (("全部交易日（2010 年以后）", range(W, N)), ("信号日", [i for i in range(W, N) if sig[i]])):
            c = []
            for n in H.values():
                f = [fwd(i, n) for i in sel if fwd(i, n) is not None]
                c.append(f"{sum(f)/len(f)*100:+.1f}% / {sum(x > 0 for x in f)/len(f)*100:.0f}%" if f else "—")
            cells.append(f"| {name} | " + " | ".join(c) + " |")
        out.append("\n| 条件 | " + " | ".join(f"之后 {k}：平均 / 上涨概率" for k in H) + " |")
        out.append("|---|" + "---|" * len(H))
        out += cells
    return "\n".join(out), keep


def checks_block(gap, n2004, rmin, rmin_d, r07, r07_d, avg_dd, pcts, keep):
    sig5 = keep[0.05][0]
    no_sig = lambda a, b: not any(sig5[i] for i in range(N) if a <= days[i] <= b)
    b_ok = [b for b, p in pcts.items() if b != "2020-03-19"]
    items = [
        ("数据", "复刻指数与 885007 公开年度收益的差距不超过 1.5 个百分点", gap <= 1.5, f"最大 {gap:.2f}"),
        ("结论 1", "以 2004-12-31 为基准，2006 年站稳 1 以上之后没有再跌破", n2004 == 0, f"{n2004} 次"),
        ("结论 1", "站稳之后比值最低点仍高于 1", rmin > 1, f"{rmin:.2f}（{rmin_d}）"),
        ("结论 1", "2007 年以后最接近跌破的一次在 2008 年", r07_d[:4] == "2008", f"{r07:.2f}（{r07_d}）"),
        ("结论 2", "历次大底（不含 2020-03）比值都处在 2006 年以来最低 20% 分位", all(pcts[b] <= 20 for b in b_ok),
         "最高 " + f"{max(pcts[b] for b in b_ok):.0f}%"),
        ("结论 3", "换基准日后的跌破，之后 3 年内平均还要再跌 10% 以上", avg_dd <= -0.10, f"{avg_dd*100:.1f}%"),
        ("结论 4", "滚动版本没有在 2015–16、2018–19 年的底部附近发出信号", no_sig("2015-06-01", "2016-06-30") and no_sig("2018-06-01", "2019-06-30"), "—"),
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


rb, gap = replica_block()
bb, n2004, rmin, rmin_d, r07, r07_d = base_block()
sb, avg_dd = sens_block()
tb, pcts = bottoms_block()
lb, keep = rolling_block()
kb, bad = checks_block(gap, n2004, rmin, rmin_d, r07, r07_d, avg_dd, pcts, keep)
doc = open(DOC, encoding="utf-8").read()
doc = fill(doc, "updated", f"数据截至 {days[-1]}，由 `tools/update.sh` 于 {datetime.date.today()} 生成。")
for name, body in (("replica", rb), ("base2004", bb), ("sensitivity", sb), ("bottoms", tb), ("rolling", lb), ("checks", kb)):
    doc = fill(doc, name, body)
open(DOC, "w", encoding="utf-8", newline="\n").write(doc)
print(f"VERIFY.md 已更新；结论复核：{'全部成立' if not bad else f'{bad} 条不成立，需要人工修改结论'}")
