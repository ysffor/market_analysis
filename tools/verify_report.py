# 专题验证的计算与文档回填：计算 docs/VERIFY.md 里所有数字，回填到 <!-- AUTO:名称 --> 标记之间，并复核结论依赖的数据条件。
# 验证 1：沪深300全收益跌破二级债基指数，就是底部？用日度数据；二级债基用按 885007 锚点校正后的序列（情景 A 为主，B、C 与未校正作对照）。
# Compute every number in docs/VERIFY.md from daily data, refill AUTO blocks, and re-check the conditions behind each conclusion.
# 用法 | usage: python -I verify_report.py <raw 目录> <build/bondfund.json> <docs/VERIFY.md>
import bisect, datetime, json, re, sys

RAW, BF, DOC = sys.argv[1:4]

# 公认的阶段性大底（沪深300），用来看比值在底部时的位置
BOTTOMS = ["2008-11-04", "2012-12-03", "2014-03-20", "2016-01-28", "2019-01-03", "2020-03-19", "2022-10-31", "2024-02-02", "2024-09-13"]
BASES = [f"{y}-12-31" for y in range(2004, 2022)]
H = {"6 个月": 122, "1 年": 244, "2 年": 488, "3 年": 732}
KEYS = {"A": ("calA", "情景 A：差距在 2004–2010 年形成"), "B": ("calB", "情景 B：差距在 2004–2019 年形成"),
        "C": ("calC", "情景 C：差距在全期均匀形成"), "raw": ("level", "未校正的复刻指数")}

csi = json.loads(open(f"{RAW}/H00300.json", "rb").read().decode("utf-8"))["data"]
eq = {f"{x['tradeDate'][:4]}-{x['tradeDate'][4:6]}-{x['tradeDate'][6:]}": x["close"] for x in csi if x["close"]}
rep = json.load(open(BF))
nf, cal = rep["n"], rep["calib"]
bk = sorted(rep["level"])
days = [d for d in sorted(eq) if "2004-12-31" <= d <= bk[-1]]
N = len(days)
E = [eq[d] for d in days]


def series(key):
    s = rep[KEYS[key][0]]
    return [s[bk[bisect.bisect_right(bk, d) - 1]] for d in days]


BS = {k: series(k) for k in KEYS}
fwd = lambda i, n: E[i + n] / E[i] - 1 if i + n < N else None
pc = lambda x: "—" if x is None else f"{x*100:+.1f}%"
idx_of = lambda d: next(i for i, x in enumerate(days) if x >= d)


def ratio(base, key):
    b0, B = idx_of(base), BS[key]
    return b0, [None] * b0 + [(E[i] / E[b0]) / (B[i] / B[b0]) for i in range(b0, N)]


def crossings(base, key):
    """实时信号：比值在 1 以上连续停留 60 个交易日（站稳）后，第一次跌到 1 以下的那一天"""
    b0, R = ratio(base, key)
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


def settled(R, start, need=60):
    run = 0
    for i in range(start, N):
        run = run + 1 if R[i] >= 1 else 0
        if run >= need:
            return i
    return None


# ---------- 复刻与校正 ----------
def replica_block():
    lv = rep["level"]
    at = lambda s, d: rep[s][bk[bisect.bisect_right(bk, d) - 1]]
    out = ["| 年份 | 885007（公开） | 复刻（未校正） | 情景 A | 情景 B | 情景 C |", "|---|---|---|---|---|---|"]
    gaps = []
    for y in range(2005, 2026):
        r = {s: (at(s, f"{y}-12-31") / at(s, f"{y-1}-12-31") - 1) * 100 for s in ("level", "calA", "calB", "calC")}
        w = cal["known"].get(str(y))
        if w is not None:
            gaps.append(abs(r["level"] - w))
        out.append(f"| {y} | {'—' if w is None else f'{w:+.2f}%'} | {r['level']:+.1f}% | {r['calA']:+.1f}% | {r['calB']:+.1f}% | {r['calC']:+.1f}% |")
    g = at("level", cal["anchor_date"]) / at("level", "2003-12-31")
    cnt = "，".join(f"{y} 年 {nf[max(k for k in bk if k[:4] == str(y))]} 只" for y in (2005, 2008, 2012, 2016, 2020, 2024))
    out.append(f"\n- 复刻（未校正）从 2003-12-31 到 {cal['anchor_date']} 增长 {g:.3f} 倍；885007 为 {cal['anchor_value']/1000:.3f} 倍，"
               f"总差距 **{cal['gap']:.3f} 倍**。在有公开数据的年份，未校正复刻与 885007 的最大差距为 {max(gaps):.2f} 个百分点。")
    out.append(f"- 纳入基金数（年末）：{cnt}，最新 {nf[bk[-1]]} 只。剔除异常数据 {rep.get('dropped', 0)} 条。")
    hits = [round(at(s, cal["anchor_date"]), 2) for s in ("calA", "calB", "calC")]
    out.append(f"- 三种情景在锚点日的点位：{hits}（应等于 {cal['anchor_value']}）。")
    return "\n".join(out), max(gaps), hits


# ---------- 各口径下的跌破（基准 2004-12-31） ----------
def scenarios_block():
    out = ["| 口径 | 站稳后跌破（实时信号日） | 之后 3 年内继续下跌 | 之后 1 年 | 最新比值 |", "|---|---|---|---|---|"]
    res = {}
    for k, (_, name) in KEYS.items():
        ev, R = crossings("2004-12-31", k)
        res[k] = (ev, R)
        if not ev:
            out.append(f"| {name} | 无 | — | — | {R[-1]:.2f} |")
        for j, e in enumerate(ev):
            out.append(f"| {name if j == 0 else ''} | {e['d']} | {e['dd']*100:.1f}%（{e['lo']}） | {pc(e['1 年'])} | {f'{R[-1]:.2f}' if j == 0 else ''} |")
    return "\n".join(out), res


# ---------- 情景 A 的细节 ----------
def base_block():
    ev, R = crossings("2004-12-31", "A")
    s = settled(R, 0)
    out = [f"- 起点之后比值先在 1 附近或以下，{days[s]} 站稳 1 以上（连续 60 个交易日）。",
           f"- 站稳之后跌破 **{len(ev)}** 次；最新比值 **{R[-1]:.2f}**（{days[-1]}）。", ""]
    out.append("| 跌破日（实时） | 之后 3 年内继续下跌 | 最低点日期 | 距最低点（交易日） | " + " | ".join(f"之后 {k}" for k in H) + " |")
    out.append("|---|---|---|---|" + "---|" * len(H))
    for e in ev:
        out.append(f"| {e['d']} | {e['dd']*100:.1f}% | {e['lo']} | {e['wait']} | " + " | ".join(pc(e[k]) for k in H) + " |")
    out.append("\n| 条件 | 天数 | " + " | ".join(f"之后 {k}：平均收益 / 上涨概率" for k in H) + " |")
    out.append("|---|---|" + "---|" * len(H))
    post = range(s, N)
    zone = {}
    for name, sel in (("站稳后的全部交易日", list(post)), ("比值 < 1（站稳后）", [i for i in post if R[i] < 1]),
                      ("比值 1–1.1（站稳后）", [i for i in post if 1 <= R[i] < 1.1]), ("比值 ≥ 1.1（站稳后）", [i for i in post if R[i] >= 1.1])):
        cells = []
        for n in H.values():
            f = [fwd(i, n) for i in sel if fwd(i, n) is not None]
            cells.append(f"{sum(f)/len(f)*100:+.1f}% / {sum(x > 0 for x in f)/len(f)*100:.0f}%" if f else "—")
            if n == 244 and f:
                zone[name] = sum(f) / len(f)
        out.append(f"| {name} | {len(sel)} | " + " | ".join(cells) + " |")
    return "\n".join(out), ev, zone


# ---------- 大底时的比值 ----------
def bottoms_block():
    Rs = {k: ratio("2004-12-31", k)[1] for k in KEYS}
    sA = settled(Rs["A"], 0)
    postA = sorted(Rs["A"][i] for i in range(sA, N))
    out = ["| 阶段底部 | 情景 A | 情景 B | 情景 C | 未校正 | 情景 A 下的历史分位 |", "|---|---|---|---|---|---|"]
    vals = {}
    for b in BOTTOMS:
        i = idx_of(b)
        vals[b] = {k: Rs[k][i] for k in KEYS}
        p = sum(v <= Rs["A"][i] for v in postA) / len(postA) * 100
        out.append(f"| {days[i]} | " + " | ".join(f"{Rs[k][i]:.2f}" for k in ("A", "B", "C", "raw")) + f" | {p:.0f}% |")
    return "\n".join(out), vals


# ---------- 换基准日（情景 A） ----------
def sens_block():
    out = ["| 基准日 | 跌破次数 | 跌破日（之后 3 年内继续下跌幅度，距最低点交易日数） | 最新比值 |", "|---|---|---|---|"]
    all_dd = []
    for b in BASES:
        ev, R = crossings(b, "A")
        all_dd += [e["dd"] for e in ev if e["i"] + 244 < N]
        out.append(f"| {b} | {len(ev)} | " + "；".join(f"{e['d']}（{e['dd']*100:.0f}%，{e['wait']}）" for e in ev) + f" | {R[-1]:.2f} |")
    avg = sum(all_dd) / len(all_dd) if all_dd else 0
    out.append(f"\n所有基准日合计 {len(all_dd)} 次跌破（之后至少有 1 年数据的），跌破后 3 年内平均还要再跌 **{abs(avg)*100:.1f}%**，"
               f"其中再跌超过 10% 的有 {sum(x <= -0.10 for x in all_dd)} 次。")
    return "\n".join(out), avg


# ---------- 滚动 5 年分位（无前视，情景 A） ----------
def rolling_block():
    W = 1220
    R = [e / b for e, b in zip(E, BS["A"])]
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
        keep[q] = sig
        keep[("ev", q)] = ev
        out.append(f"\n**比值处在过去 5 年最低 {int(q*100)}% 区间**：首次信号 {len(ev)} 次，信号日共 {sum(sig)} 天。\n")
        out.append("| 首次信号日 | 之后 3 年内继续下跌 | 最低点日期 | " + " | ".join(f"之后 {k}" for k in H) + " |")
        out.append("|---|---|---|" + "---|" * len(H))
        for i in ev:
            lo = min(range(i, min(N, i + 732)), key=lambda j: E[j])
            out.append(f"| {days[i]} | {(E[lo]/E[i]-1)*100:.1f}% | {days[lo]} | " + " | ".join(pc(fwd(i, n)) for n in H.values()) + " |")
        out.append("\n| 条件 | " + " | ".join(f"之后 {k}：平均 / 上涨概率" for k in H) + " |")
        out.append("|---|" + "---|" * len(H))
        for name, sel in (("全部交易日（2010 年以后）", range(W, N)), ("信号日", [i for i in range(W, N) if sig[i]])):
            c = []
            for n in H.values():
                f = [fwd(i, n) for i in sel if fwd(i, n) is not None]
                c.append(f"{sum(f)/len(f)*100:+.1f}% / {sum(x > 0 for x in f)/len(f)*100:.0f}%" if f else "—")
            out.append(f"| {name} | " + " | ".join(c) + " |")
    return "\n".join(out), keep


def checks_block(gap, hits, res, evA, zone, bvals, avg_dd, keep):
    sig5 = keep[0.05]
    no_sig = lambda a, b: not any(sig5[i] for i in range(N) if a <= days[i] <= b)
    since08 = [b for b in BOTTOMS if b != "2020-03-19"]
    rng = [bvals[b][k] for b in since08 for k in ("A", "B", "C")]
    after15 = [bvals[b]["A"] for b in BOTTOMS if b >= "2015-01-01" and b != "2020-03-19"]
    lift = zone.get("比值 1–1.1（站稳后）", 0) - zone.get("站稳后的全部交易日", 0)
    items = [
        ("数据", "未校正复刻与 885007 公开年度收益的差距不超过 1.5 个百分点", gap <= 1.5, f"最大 {gap:.2f}"),
        ("数据", "三种校正情景都正好经过 885007 锚点", all(abs(h - cal["anchor_value"]) < 1 for h in hits), f"{hits}"),
        ("结论 1", "未校正时站稳后没有跌破、校正后（情景 A）至少跌破 2 次，即口径决定结论", not res["raw"][0] and len(res["A"][0]) >= 2,
         f"未校正 {len(res['raw'][0])} 次，A {len(res['A'][0])} 次"),
        ("结论 2", "三种情景下，2008 年以来的大底（不含 2020-03）比值都在 0.90–1.12 之间", all(0.90 <= v <= 1.12 for v in rng), f"{min(rng):.2f}–{max(rng):.2f}"),
        ("结论 2", "情景 A 下，比值在 1–1.1 之间时之后 1 年平均收益比全部交易日高 20 个百分点以上", lift >= 0.20, f"高 {lift*100:.1f} 个百分点"),
        ("结论 3", "情景 A 下每次跌破后 3 年内继续下跌都不超过 5%", bool(evA) and all(e["dd"] >= -0.05 for e in evA),
         f"最多 {abs(min(e['dd'] for e in evA))*100:.1f}%" if evA else "无跌破"),
        ("结论 3", "情景 A 下 2015 年以后的大底（不含 2020-03）比值都高于 1，即没有跌破", all(v > 1 for v in after15), f"最低 {min(after15):.2f}"),
        ("结论 3", "情景 B、C 下站稳后没有跌破", not res["B"][0] and not res["C"][0], f"B {len(res['B'][0])} 次，C {len(res['C'][0])} 次"),
        ("结论 4", "换基准日后的跌破，之后 3 年内平均还要再跌 10% 以上", avg_dd <= -0.10, f"{abs(avg_dd)*100:.1f}%"),
        ("结论 5", "滚动版本没有在 2015–16、2018–19 年的底部附近发出信号", no_sig("2015-06-01", "2016-06-30") and no_sig("2018-06-01", "2019-06-30"), "—"),
        ("结论 5", "滚动版本（最低 5%）的首次信号只落在 2011–12 年和 2022–24 年两段",
         all(days[i][:4] in ("2011", "2012", "2022", "2023", "2024") for i in keep[("ev", 0.05)]),
         "、".join(days[i][:7] for i in keep[("ev", 0.05)])),
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


rb, gap, hits = replica_block()
cb, res = scenarios_block()
bb, evA, zone = base_block()
tb, bvals = bottoms_block()
sb, avg_dd = sens_block()
lb, keep = rolling_block()
kb, bad = checks_block(gap, hits, res, evA, zone, bvals, avg_dd, keep)
doc = open(DOC, encoding="utf-8").read()
doc = fill(doc, "updated", f"数据截至 {days[-1]}，由 `tools/update.sh` 于 {datetime.date.today()} 生成。")
for name, body in (("replica", rb), ("scenarios", cb), ("base2004", bb), ("bottoms", tb), ("sensitivity", sb), ("rolling", lb), ("checks", kb)):
    doc = fill(doc, name, body)
open(DOC, "w", encoding="utf-8", newline="\n").write(doc)
print(f"VERIFY.md 已更新；结论复核：{'全部成立' if not bad else f'{bad} 条不成立，需要人工修改结论'}")
