# 下载人民币流动性与中美传导分析所需的国内数据到 raw/cn/（只放下载文件）
# - 中国货币网（全国银行间同业拆借中心）：回购定盘利率 FR007 / DR007（FDR007）、SHIBOR，日度，每次请求最多 1 年，按年循环
# - 东方财富数据中心：M2/M1、新增人民币贷款、外汇储备、PMI、CPI（月度），中美国债收益率（日度），存款准备金率、LPR（调整记录）
# Download Chinese liquidity data into raw/cn/: CFETS repo fixings and SHIBOR (yearly chunks), Eastmoney macro tables (paged).
# 用法 | usage: python -I fetch_cn.py <raw 目录>
import datetime, json, os, sys, time, urllib.request

OUT = os.path.join(sys.argv[1], "cn")
os.makedirs(OUT, exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
START_YEAR = 2010
TODAY = datetime.date.today()


def get(url, referer):
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": referer})
            return json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8"))
        except Exception as e:  # 网络偶发失败时重试
            last = e
            time.sleep(1 + attempt * 2)
    raise RuntimeError(f"下载失败：{url}：{last}")


# ---- 中国货币网：按年下载 ----
def chinamoney(kind):
    path = {"repo": "cm-u-bk-currency/FrrHis", "shibor": "cm-u-bk-shibor/ShiborHis"}[kind]
    rows = {}
    for y in range(START_YEAR, TODAY.year + 1):
        a, b = f"{y}-01-01", min(f"{y}-12-31", TODAY.isoformat())
        d = get(f"https://www.chinamoney.com.cn/ags/ms/{path}?lang=CN&startDate={a}&endDate={b}", "https://www.chinamoney.com.cn/")
        for r in d.get("records") or []:
            if kind == "repo":
                m = r.get("frValueMap") or {}
                if m.get("date"):
                    rows[m["date"]] = {k: m.get(k) for k in ("FR001", "FR007", "FR014", "FDR001", "FDR007", "FDR014")}
            else:
                if r.get("showDateCN"):
                    rows[r["showDateCN"]] = {k: r.get(k) for k in ("ON", "1W", "2W", "1M", "3M", "6M", "9M", "1Y")}
        time.sleep(0.3)
    if len(rows) < 1000:
        sys.exit(f"中国货币网 {kind} 只取到 {len(rows)} 天，接口可能变了")
    json.dump(rows, open(os.path.join(OUT, f"{kind}.json"), "w"), separators=(",", ":"))
    print(f"中国货币网 {kind}：{min(rows)} → {max(rows)}，{len(rows)} 天")


# ---- 东方财富：按页下载整张表 ----
EM = {  # 文件名: (报表名, 排序列)
    "money_supply": ("RPT_ECONOMY_CURRENCY_SUPPLY", "REPORT_DATE"),
    "rmb_loan": ("RPT_ECONOMY_RMB_LOAN", "REPORT_DATE"),
    "fx_reserves": ("RPT_ECONOMY_GOLD_CURRENCY", "REPORT_DATE"),
    "pmi": ("RPT_ECONOMY_PMI", "REPORT_DATE"),
    "cpi": ("RPT_ECONOMY_CPI", "REPORT_DATE"),
    "rrr": ("RPT_ECONOMY_DEPOSIT_RESERVE", "REPORT_DATE"),
    "lpr": ("RPTA_WEB_RATE", "TRADE_DATE"),
    "bond_yields": ("RPTA_WEB_TREASURYYIELD", "SOLAR_DATE"),
}


def eastmoney(name, report, sort):
    rows, page = [], 1
    while True:
        d = get(f"https://datacenter-web.eastmoney.com/api/data/v1/get?reportName={report}&columns=ALL&pageSize=500"
                f"&pageNumber={page}&sortColumns={sort}&sortTypes=-1", "https://data.eastmoney.com/")
        r = d.get("result")
        if not r:
            sys.exit(f"东方财富 {report} 返回为空：{d.get('message')}")
        rows += r["data"]
        if page >= r["pages"]:
            break
        page += 1
        time.sleep(0.3)
    json.dump(rows, open(os.path.join(OUT, f"{name}.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    dates = sorted(str(x.get(sort))[:10] for x in rows)
    print(f"东方财富 {name}：{dates[0]} → {dates[-1]}，{len(rows)} 条")


chinamoney("repo")
chinamoney("shibor")
for name, (report, sort) in EM.items():
    eastmoney(name, report, sort)
