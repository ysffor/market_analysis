# 以 15 天为步长，从今天往回 20 年，取每个采样日当日或之前最近的一个交易日值，输出页面内嵌用的 JSON
# Sample every 15 days back 20 years from today (as-of last observation), emit the JSON embedded in the page
# 用法 | usage: python -I sample.py <raw 目录> <build/bondfund.json> [YYYY-MM-DD 截止日，默认今天] > data.json
import csv, json, datetime, bisect, sys
src = sys.argv[1]
def fred(name):
    out = {}
    for r in csv.DictReader(open(f"{src}/{name}.csv")):
        v = r[name]
        if v not in ("", "."): out[r["observation_date"]] = float(v)
    return out
def yahoo():
    d = json.load(open(f"{src}/gold_yf.json"))["chart"]["result"][0]
    out = {}
    for t, c in zip(d["timestamp"], d["indicators"]["quote"][0]["close"]):
        if c is not None:
            out[datetime.datetime.fromtimestamp(t, datetime.timezone.utc).date().isoformat()] = round(c, 1)
    return out
series = {"gold": yahoo(), "oil": fred("DCOILWTICO"), "y10": fred("DGS10"),
          "real": fred("DFII10"), "be": fred("T10YIE"), "dxy": fred("DTWEXBGS"),
          "walcl": fred("WALCL"), "tga": fred("WTREGEN"), "rrp": fred("RRPONTSYD")}
today = datetime.date.fromisoformat(sys.argv[3]) if len(sys.argv) > 3 else datetime.date.today()
start = today.replace(year=today.year - 20)
dates = []
d = today
while d >= start:
    dates.append(d); d -= datetime.timedelta(days=15)
dates.reverse()
res = {"dates": [x.isoformat() for x in dates], "asof": {}}
for k, s in series.items():
    keys = sorted(s)
    vals = []
    for x in dates:
        i = bisect.bisect_right(keys, x.isoformat()) - 1
        vals.append(s[keys[i]] if i >= 0 else None)
    res[k] = vals
    res["asof"][k] = keys[-1]
# 净流动性 = 美联储总资产 − TGA − 隔夜逆回购，单位万亿美元 | net liquidity = Fed assets − TGA − ON RRP, $tn
fed = [round(w / 1e6, 3) for w in res["walcl"]]
res["netliq"] = [round(w / 1e6 - g / 1e6 - (r or 0) / 1e3, 3) for w, g, r in zip(res["walcl"], res["tga"], res["rrp"])]
res["asof"]["netliq"] = min(res["asof"]["walcl"], res["asof"]["tga"], res["asof"]["rrp"])
res["walcl"] = fed
res["tga"] = [round(g / 1e6, 3) for g in res["tga"]]
res["rrp"] = [round((r or 0) / 1e3, 5) for r in res["rrp"]]  # 余额可能只有几亿美元，多保留两位

# 专题验证：沪深300全收益与二级债基复刻指数，自 2004-12-31 起按周抽样（每周最后一个交易日），两者都以基准日 = 1000
# Verification section: CSI 300 TR vs replicated secondary-bond-fund index, weekly since 2004-12-31, both rebased to 1000
csi = json.loads(open(f"{src}/H00300.json", "rb").read().decode("utf-8"))["data"]
eq = {f"{x['tradeDate'][:4]}-{x['tradeDate'][4:6]}-{x['tradeDate'][6:]}": x["close"] for x in csi if x["close"]}
bfj = json.load(open(sys.argv[2]))
bk = sorted(bfj["level"])
days = [d for d in sorted(eq) if "2004-12-31" <= d <= today.isoformat()]
def bf_at(d, key="level"):
    i = bisect.bisect_right(bk, d) - 1
    return bfj[key][bk[i]]
wk = lambda d: datetime.date.fromisoformat(d).isocalendar()[:2]
vd = [d for i, d in enumerate(days) if i == len(days) - 1 or wk(d) != wk(days[i + 1])]
e0 = eq[days[0]]
# bf = 未校正的复刻指数；bfA/bfB/bfC = 按 885007 锚点校正后的三种情景（见 replica.py）
res["verify"] = {"d": vd, "eq": [round(eq[d] / e0 * 1000, 1) for d in vd]}
for out_key, key in (("bf", "level"), ("bfA", "calA"), ("bfB", "calB"), ("bfC", "calC")):
    b0 = bf_at(days[0], key)
    res["verify"][out_key] = [round(bf_at(d, key) / b0 * 1000, 1) for d in vd]
res["asof"]["verify"] = min(days[-1], bk[-1])
json.dump(res, sys.stdout, separators=(",", ":"))
