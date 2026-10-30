# A 股成交额专题：下载数据到 raw/ashare/（只放下载文件）
# - 中证指数官网：中证全指（000985）日收盘与成交额（亿元），代表全 A 股成交额
# - 东方财富数据中心：两融每日数据（融资余额、融资买入额、两融交易额占比），新股发行明细（净募资额）
# - 上交所：主要宽基 ETF 的份额（每周最后一个交易日），用来观察"国家队"等大资金通过 ETF 的申赎
# A-share turnover study: CSI All-Share turnover, margin data, IPO details (Eastmoney), weekly SSE ETF shares.
# 用法 | usage: python -I fetch_ashare.py <raw 目录>
import datetime, json, os, sys, time, urllib.request

OUT = os.path.join(sys.argv[1], "ashare")
os.makedirs(OUT, exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
TODAY = datetime.date.today()
ETF_START = "2024-01-01"
ETFS = {"510050": "上证50（华夏）", "510180": "上证180（华安）", "510300": "沪深300（华泰柏瑞）", "510310": "沪深300（易方达）",
        "510330": "沪深300（华夏）", "510500": "中证500（南方）", "512100": "中证1000（南方）", "588000": "科创50（华夏）",
        "588080": "科创50（易方达）"}


def get(url, referer, enc="utf-8"):
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": referer})
            return json.loads(urllib.request.urlopen(req, timeout=60).read().decode(enc, "replace"))
        except Exception as e:      # 网络偶发失败时重试
            last = e
            time.sleep(1 + attempt * 2)
    raise RuntimeError(f"下载失败：{url}：{last}")


# ---- 中证全指 ----
d = get(f"https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=000985&startDate=20190101&endDate={TODAY:%Y%m%d}",
        "https://www.csindex.com.cn/")
rows = {f"{x['tradeDate'][:4]}-{x['tradeDate'][4:6]}-{x['tradeDate'][6:]}": {"close": x["close"], "amt": x["tradingValue"]}
        for x in d["data"] if x.get("close") and x.get("tradingValue")}
if len(rows) < 1000:
    sys.exit(f"中证全指只取到 {len(rows)} 天，接口可能变了")
json.dump(rows, open(os.path.join(OUT, "csi_all.json"), "w"), separators=(",", ":"))
print(f"中证全指：{min(rows)} → {max(rows)}，{len(rows)} 天")


# ---- 东方财富：按页下载 ----
def eastmoney(name, report, sort, cols):
    out, page = [], 1
    while True:
        r = get(f"https://datacenter-web.eastmoney.com/api/data/v1/get?reportName={report}&columns=ALL&pageSize=500"
                f"&pageNumber={page}&sortColumns={sort}&sortTypes=-1", "https://data.eastmoney.com/").get("result")
        if not r:
            sys.exit(f"东方财富 {report} 返回为空")
        out += [{k: x.get(k) for k in cols} for x in r["data"]]
        if page >= r["pages"]:
            break
        page += 1
        time.sleep(0.3)
    json.dump(out, open(os.path.join(OUT, f"{name}.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    ds = sorted(str(x[sort])[:10] for x in out if x.get(sort))
    print(f"东方财富 {name}：{ds[0]} → {ds[-1]}，{len(out)} 条")


eastmoney("margin", "RPTA_WEB_MARGIN_DAILYTRADE", "STATISTICS_DATE",
          ["STATISTICS_DATE", "FIN_BALANCE", "MARGIN_BALANCE", "FIN_BUY_AMT", "MARGIN_TRADE_AMT", "TRADE_AMT_RATIO", "BALANCE_RATIO"])
eastmoney("ipo", "RPTA_APP_IPOAPPLY", "APPLY_DATE",
          ["SECURITY_CODE", "SECURITY_NAME", "APPLY_DATE", "LISTING_DATE", "MARKET_TYPE_NEW", "NETSUMFINA"])

# ---- 上交所 ETF 份额：每周最后一个交易日 ----
days = sorted(d for d in rows if d >= ETF_START)
wk = lambda s: datetime.date.fromisoformat(s).isocalendar()[:2]
fridays = [s for i, s in enumerate(days) if i == len(days) - 1 or wk(s) != wk(days[i + 1])]
path = os.path.join(OUT, "etf_shares.json")
etf = json.load(open(path)) if os.path.exists(path) else {}
for s in fridays:
    if s in etf and s != fridays[-1]:      # 已下载过的历史日期不再重复请求
        continue
    r = get(f"http://query.sse.com.cn/commonQuery.do?isPagination=true&pageHelp.pageSize=3000&pageHelp.pageNo=1"
            f"&sqlId=COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L&STAT_DATE={s}", "http://www.sse.com.cn/")
    data = r.get("pageHelp", {}).get("data") or []
    got = {x["SEC_CODE"]: float(x["TOT_VOL"]) for x in data if x.get("SEC_CODE") in ETFS and x.get("TOT_VOL")}
    if got:
        etf[s] = got                        # 万份
    time.sleep(0.3)
json.dump(etf, open(path, "w"), separators=(",", ":"))
print(f"上交所 ETF 份额：{min(etf)} → {max(etf)}，{len(etf)} 周")
json.dump(ETFS, open(os.path.join(OUT, "etf_list.json"), "w", encoding="utf-8"), ensure_ascii=False)

# ---- 东方财富：ETF 周收盘价（不复权），用来把份额变化换算成金额、识别份额拆分或合并 ----
px = {}
for c in ETFS:
    r = get(f"https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=1.{c}&klt=102&fqt=0&beg={ETF_START.replace('-', '')}"
            f"&end={TODAY:%Y%m%d}&fields1=f1,f2,f3&fields2=f51,f53", "https://quote.eastmoney.com/")
    kl = (r.get("data") or {}).get("klines") or []
    px[c] = {k.split(",")[0]: float(k.split(",")[1]) for k in kl}
    if len(px[c]) < 50:
        sys.exit(f"ETF {c} 价格只取到 {len(px[c])} 周")
    time.sleep(0.3)
json.dump(px, open(os.path.join(OUT, "etf_price.json"), "w"), separators=(",", ":"))
print(f"ETF 周收盘价：{len(px)} 只")
