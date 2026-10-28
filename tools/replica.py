# 专题验证用：按万得 885007 的规则复刻二级债基指数——全部二级债基每日等权，成立满 91 天后纳入；
# 每日收益用 equityReturn（含分红的日增长率）。输出每日点位（基点 1000）和当日纳入的基金数。
# Replicate Wind 885007: daily equal-weight of all secondary bond funds (included 91 days after inception).
# 用法 | usage: python -I replica.py <raw/funds 目录> <输出 bondfund.json>
import datetime, json, os, re, sys

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
json.dump({"level": level, "n": n, "dropped": bad}, open(out, "w"), separators=(",", ":"))
ks = sorted(level)
print(f"二级债基复刻指数：{ks[0]} → {ks[-1]}，最新纳入 {n[ks[-1]]} 只基金，剔除异常数据 {bad} 条")
