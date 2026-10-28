# 专题验证用：按万得 885007 的规则复刻二级债基指数——全部二级债基每日等权，成立满 91 天后纳入；
# 每日收益用 equityReturn（含分红的日增长率）。输出每日点位（基点 1000）、当日纳入的基金数，以及按 885007 锚点校正后的三种情景序列。
# Replicate Wind 885007: daily equal-weight of all secondary bond funds (included 91 days after inception).
# 用法 | usage: python -I replica.py <raw/funds 目录> <输出 bondfund.json>
import datetime, json, math, os, re, sys

navdir, out = sys.argv[1], sys.argv[2]
CN = datetime.timezone(datetime.timedelta(hours=8))
daily, bad = {}, 0
for fn in sorted(os.listdir(navdir)):
    t = open(f"{navdir}/{fn}", encoding="utf-8", errors="replace").read()
    m = re.search(r"Data_netWorthTrend\s*=\s*(\[.*?\]);", t, re.S)
    if not m:
        continue
    rows = json.loads(m.group(1))
    if len(rows) < 30:
        continue
    t0 = rows[0]["x"]
    for r in rows[1:]:
        er = r.get("equityReturn")
        if er in (None, ""):
            continue
        er = float(er)
        if abs(er) > 15:          # 明显异常的数据（二级债基单日涨跌不会超过 15%）
            bad += 1
            continue
        if r["x"] - t0 < 91 * 86400000:
            continue
        d = datetime.datetime.fromtimestamp(r["x"] / 1000, CN).strftime("%Y-%m-%d")
        daily.setdefault(d, []).append(er)
level, n, v = {}, {}, 1000.0
for d in sorted(daily):
    v *= 1 + sum(daily[d]) / len(daily[d]) / 100
    level[d] = round(v, 4)
    n[d] = len(daily[d])
ks = sorted(level)

# ---- 按 885007 锚点校正 ----
# 用天天基金现存基金重建的指数会系统性低估 885007（早年样本少、缺已清盘或已转型的基金）。
# 校正方法：885007 在 ANCHOR_DATE 的点位（基日 2003-12-31 = 1000）给出总差距；已知年度收益的年份按实际差距逐年校正，
# 剩余差距按情景均匀分配到各自窗口内的其他年份，年内按时间线性（对数）分配。锚点之后差距保持不变。
# Calibrate to Wind 885007: total gap from the anchor; known years corrected exactly; remainder spread by scenario.
ANCHOR_DATE, ANCHOR_VALUE = "2026-10-16", 5163.65   # 来源见 docs/VERIFY.md
W885007 = {2013: 0.39, 2020: 9.12, 2021: 7.82, 2022: -5.07, 2023: 0.57, 2024: 4.90}
SCENARIOS = {"calA": (2004, 2010), "calB": (2004, 2019), "calC": (2004, 2026)}
at = lambda d: level[max(k for k in ks if k <= d)]
D0 = "2003-12-31"
yret = {y: at(f"{y}-12-31") / at(f"{y-1}-12-31") for y in range(2004, 2026)}
total = math.log(ANCHOR_VALUE / 1000 / (at(ANCHOR_DATE) / at(D0)))
known = {y: math.log((1 + w / 100) / yret[y]) for y, w in W885007.items()}
cal = {}
for name, (y0, y1) in SCENARIOS.items():
    free = [y for y in range(y0, y1 + 1) if y not in known]
    per = (total - sum(known.values())) / len(free)
    logf = {y: known.get(y, per if y in free else 0.0) for y in range(2004, 2027)}

    def factor(d):
        y = int(d[:4])
        if d > ANCHOR_DATE:
            d, y = ANCHOR_DATE, int(ANCHOR_DATE[:4])
        if y < 2004:
            return 1.0
        start = datetime.date(y, 1, 1).toordinal()
        end = (datetime.date.fromisoformat(ANCHOR_DATE) if y == int(ANCHOR_DATE[:4]) else datetime.date(y, 12, 31)).toordinal()
        frac = min(1.0, (datetime.date.fromisoformat(d).toordinal() - start + 1) / (end - start + 1))
        return math.exp(sum(logf[z] for z in range(2004, y)) + logf[y] * frac)

    base = at(D0)
    cal[name] = {d: round(level[d] / base * 1000 * factor(d), 4) for d in ks}
    got = cal[name][max(k for k in ks if k <= ANCHOR_DATE)]
    assert abs(got - ANCHOR_VALUE) < 1, (name, got)

json.dump({"level": level, "n": n, "dropped": bad, **cal,
           "calib": {"anchor_date": ANCHOR_DATE, "anchor_value": ANCHOR_VALUE, "gap": round(math.exp(total), 4),
                     "known": W885007, "scenarios": {k: list(v) for k, v in SCENARIOS.items()}}},
          open(out, "w"), separators=(",", ":"))
print(f"二级债基复刻指数：{ks[0]} → {ks[-1]}，最新纳入 {n[ks[-1]]} 只基金，剔除异常数据 {bad} 条；"
      f"相对 885007 的总差距 {math.exp(total):.3f} 倍")
