# A 股信号日报：每个交易日跟踪 A 股成交额专题（docs/ashare/REPORT.md）里列出的短期信号——成交额、宽基 ETF 资金进出、融资余额、
# 10 年期美债收益率，以及指数位置；政策通报靠人工查看（只给链接）。生成 docs/watch/signals_<交易日>.md，并更新目录 docs/watch/README.md。
# 由 Windows 计划任务在工作日早上运行（注册脚本 tools/watch_task.ps1），覆盖上一个交易日的完整数据。
# Daily A-share signal report: turnover, broad-ETF flows, margin balance, US 10Y yield, index position → docs/watch/signals_<date>.md.
# 用法 | usage: python -I watch.py <仓库根目录> [--retry N] [--wait 秒] [--force]
#   两融和 ETF 份额通常在下一个交易日早上才公布；没到齐时每隔 --wait 秒重试，最多 --retry 次，仍没到齐就照常出报告并注明数据日期。
import argparse, bisect, datetime, json, math, os, sys, time, traceback, urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("root")
ap.add_argument("--retry", type=int, default=3)
ap.add_argument("--wait", type=int, default=600)
ap.add_argument("--force", action="store_true", help="报告已存在且数据齐全时也重新生成")
args = ap.parse_args()
RAW = os.path.join(args.root, "raw", "watch")
OUT = os.path.join(args.root, "docs", "watch")
os.makedirs(RAW, exist_ok=True)
os.makedirs(OUT, exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
# 与 tools/fetch_ashare.py 的 ETFS 保持一致
ETFS = {"510050": "上证50（华夏）", "510180": "上证180（华安）", "510300": "沪深300（华泰柏瑞）", "510310": "沪深300（易方达）",
        "510330": "沪深300（华夏）", "510500": "中证500（南方）", "512100": "中证1000（南方）", "588000": "科创50（华夏）",
        "588080": "科创50（易方达）"}
LOOKBACK = 30           # 报告用到的交易日数（ETF 份额按日缓存）
LOG = open(os.path.join(RAW, "run.log"), "a", encoding="utf-8")


def log(msg):
    LOG.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")
    LOG.flush()


def get(url, referer):
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": referer})
            return json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace"))
        except Exception as e:      # 网络偶发失败时重试
            last = e
            time.sleep(2 + attempt * 3)
    raise RuntimeError(f"下载失败：{url}：{last}")


def eastmoney(report, sort, n):
    r = get(f"https://datacenter-web.eastmoney.com/api/data/v1/get?reportName={report}&columns=ALL&pageSize={n}"
            f"&pageNumber=1&sortColumns={sort}&sortTypes=-1", "https://data.eastmoney.com/")["result"]["data"]
    return {x[sort][:10]: x for x in r}


def fetch():
    today = datetime.date.today()
    d = get(f"https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=000985&startDate=20250101&endDate={today:%Y%m%d}",
            "https://www.csindex.com.cn/")["data"]
    csi = {f"{x['tradeDate'][:4]}-{x['tradeDate'][4:6]}-{x['tradeDate'][6:]}": (x["close"], x["tradingValue"])
           for x in d if x.get("close") and x.get("tradingValue")}
    days = sorted(csi)
    recent = days[-LOOKBACK:]
    mg = {k: v["FIN_BALANCE"] for k, v in eastmoney("RPTA_WEB_MARGIN_DAILYTRADE", "STATISTICS_DATE", 60).items() if v.get("FIN_BALANCE")}
    ust = {k: v["EMG00001310"] for k, v in eastmoney("RPTA_WEB_TREASURYYIELD", "SOLAR_DATE", 60).items() if v.get("EMG00001310")}
    # 上交所 ETF 份额（万份），按交易日缓存；最近一天每次都重新请求，因为可能还没公布
    path = os.path.join(RAW, "etf_daily.json")
    etf = json.load(open(path)) if os.path.exists(path) else {}
    for s in recent:
        if s in etf and s != recent[-1]:
            continue
        r = get(f"http://query.sse.com.cn/commonQuery.do?isPagination=true&pageHelp.pageSize=3000&pageHelp.pageNo=1"
                f"&sqlId=COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L&STAT_DATE={s}", "http://www.sse.com.cn/")
        got = {x["SEC_CODE"]: float(x["TOT_VOL"]) for x in (r.get("pageHelp", {}).get("data") or [])
               if x.get("SEC_CODE") in ETFS and x.get("TOT_VOL")}
        if len(got) == len(ETFS):
            etf[s] = got
        time.sleep(0.3)
    json.dump(etf, open(path, "w"), separators=(",", ":"))
    # ETF 日收盘价（不复权），腾讯行情
    px = {}
    for c in ETFS:
        r = get(f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh{c},day,{recent[0]},{recent[-1]},{LOOKBACK + 5},",
                "https://gu.qq.com/")
        px[c] = {k[0]: float(k[2]) for k in r["data"][f"sh{c}"].get("day", [])}
        time.sleep(0.2)
    return csi, days, mg, ust, etf, px


def etf_flows(days, etf, px):
    """每日资金净流入（亿元）= 份额变化（亿份）× 当日收盘价；份额变化超过约 35% 且前后一天价格反向跳动超过约 35% 的视为拆分合并，不计入"""
    ek = [d for d in days if d in etf]
    flow, splits = {}, []
    for i in range(1, len(ek)):
        a, b, tot = etf[ek[i - 1]], etf[ek[i]], 0.0
        for c in ETFS:
            if not a.get(c) or not b.get(c) or ek[i] not in px[c]:
                continue
            ls = math.log(b[c] / a[c])
            if abs(ls) > 0.3:
                ks = sorted(px[c])
                j = ks.index(ek[i])
                rs = [math.log(px[c][ks[k]] / px[c][ks[k - 1]]) for k in (j - 1, j, j + 1) if 1 <= k < len(ks)]
                if any(abs(r) > 0.3 and (r > 0) != (ls > 0) for r in rs):
                    splits.append((c, ek[i]))
                    continue
            tot += (b[c] - a[c]) / 1e4 * px[c][ek[i]]
        flow[ek[i]] = tot
    return flow, splits


def asof(series, d):
    """不晚于 d 的最近一个数据点"""
    ks = sorted(series)
    i = bisect.bisect_right(ks, d) - 1
    return (ks[i], series[ks[i]]) if i >= 0 else (None, None)


def build(csi, days, mg, ust, etf, px):
    T = days[-1]
    P = [csi[d][0] for d in days]
    A = [csi[d][1] for d in days]
    n = len(days)
    chg = lambda i: (P[i] / P[i - 1] - 1) * 100
    ipk = max(range(n), key=lambda i: P[i])
    ma20 = sum(P[-20:]) / 20
    a5, a20 = sum(A[-5:]) / 5, sum(A[-20:]) / 20
    flow, splits = etf_flows(days, etf, px)
    fk = sorted(flow)
    f5 = sum(flow[d] for d in fk[-5:])
    fm = sum(v for d, v in flow.items() if d[:7] == T[:7])
    mk = sorted(mg)
    m_d, m_v = asof(mg, T)
    m_prev5 = mg[mk[max(0, mk.index(m_d) - 5)]] if m_d else None
    u_d, u_v = asof(ust, T)
    uk = sorted(ust)
    u_prev5 = ust[uk[max(0, uk.index(u_d) - 5)]] if u_d else None
    e_d = fk[-1] if fk else None

    # 信号判断：规则写在报告里，改规则只改这里
    sig = []
    if a5 >= 20000:
        s = "积极：放量"
    elif a5 >= 15000:
        s = "中性"
    else:
        s = "偏弱：缩量"
    day = ""
    if A[-1] > 1.2 * a20:
        day = "；当日放量上涨" if chg(n - 1) > 0 else "；当日放量下跌"
    sig.append(("成交额", f"当日 {A[-1]:,.0f} 亿元，5 日均 {a5:,.0f}，20 日均 {a20:,.0f}", s + day,
                "5 日均 ≥ 2 万亿为放量，1.5–2 万亿为中性，低于 1.5 万亿为缩量；当日成交额超过 20 日均 1.2 倍时标注放量涨跌"))
    sig.append(("宽基 ETF 资金", f"最近 5 日 {f5:+,.0f} 亿元，本月 {fm:+,.0f} 亿元（截至 {e_d}）",
                "积极：净流入，托底继续" if f5 > 0 else "偏弱：净流出，托底减弱", "最近 5 个交易日合计净流入为正即托底继续"))
    if m_d:
        dm = m_v - m_prev5
        sig.append(("融资余额", f"{m_v:,.0f} 亿元，5 日 {dm:+,.0f}（截至 {m_d}）",
                    "积极：止跌回升" if dm >= 0 else "偏弱：仍在下降", "最近 5 个交易日变化 ≥ 0 为止跌"))
    if u_d:
        du = (u_v - u_prev5) * 100
        s = "偏弱：压力加大" if u_v >= 5.2 else ("积极：压力缓和" if u_v < 4.8 else "中性：仍在高位")
        sig.append(("10 年期美债收益率", f"{u_v:.2f}%，5 日 {du:+.0f} 个基点（截至 {u_d}）", s,
                    "≥ 5.2% 压力加大，4.8%–5.2% 仍在高位，低于 4.8% 压力缓和"))
    above = P[-1] >= ma20
    sig.append(("指数位置", f"中证全指 {P[-1]:,.0f}（{chg(n - 1):+.2f}%），距 {days[ipk]} 高点 {(P[-1] / P[ipk] - 1) * 100:+.1f}%，20 日均线 {ma20:,.0f}",
                "积极：站上 20 日均线" if above else "偏弱：在 20 日均线下方", "收盘价与 20 日均线比较"))
    complete = m_d == T and e_d == T

    pos = sum(s[2].startswith("积极") for s in sig)
    neg = sum(s[2].startswith("偏弱") for s in sig)
    out = [f"# A 股信号日报 {T}", "",
           f"数据截至 {T} 收盘，生成于 {datetime.datetime.now():%Y-%m-%d %H:%M}。信号来自 [A 股成交额专题](../ashare/REPORT.md)；"
           "这是按固定规则整理的数据，不是预测，也不构成投资建议。", "",
           f"**{len(sig)} 个信号中，积极 {pos} 个、偏弱 {neg} 个、中性 {len(sig) - pos - neg} 个。**"
           + ("" if complete else "（部分数据还没公布，见各行的\"截至\"日期。）"), "",
           "| 信号 | 最新 | 判断 | 规则 |", "|---|---|---|---|"]
    out += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in sig]
    out += ["", "## 政策通报（人工查看）", "",
            "脚本不抓新闻。重点看稳市场工具（证券、基金、保险公司互换便利，股票回购增持再贷款）有没有新增额度、放宽条件或公布操作量：", "",
            "- [中国人民银行 新闻发布](http://www.pbc.gov.cn/goutongjiaoliu/113456/113469/index.html)",
            "- [中国证监会 新闻发布](http://www.csrc.gov.cn/csrc/c100028/common_list.shtml)",
            "- [国家金融监督管理总局 新闻发布](https://www.nfra.gov.cn/cn/view/pages/ItemList.html?itemPId=914&itemId=915)", "",
            "## 最近 10 个交易日", "",
            "| 日期 | 中证全指 | 涨跌 | 成交额（亿元） | 宽基 ETF 净流入（亿元） | 融资余额（亿元） | 10 年期美债（%） |",
            "|---|---|---|---|---|---|---|"]
    for i in range(n - 1, n - 11, -1):
        d = days[i]
        f = f"{flow[d]:+,.0f}" if d in flow else "—"
        m = f"{mg[d]:,.0f}" if d in mg else "—"
        u = f"{ust[d]:.2f}" if d in ust else "—"
        out.append(f"| {d} | {P[i]:,.0f} | {chg(i):+.2f}% | {A[i]:,.0f} | {f} | {m} | {u} |")
    out += ["", "## 说明", "",
            "- 中证全指和成交额来自中证指数官网；融资余额、美债收益率来自东方财富数据中心；宽基 ETF 份额来自上交所，收盘价来自腾讯行情。",
            "- 宽基 ETF 为上交所 9 只主要宽基（上证50、上证180、沪深300 三只、中证500、中证1000、科创50 两只），资金净流入 = 份额变化 × 当日收盘价；"
            "深交所的宽基 ETF 没有纳入。"
            + ("" if not splits else " 识别为份额拆分或合并、没有计入的：" + "、".join(f"{c} {d}" for c, d in splits) + "。"),
            "- 两融和 ETF 份额一般在下一个交易日早上公布，美债收益率是美国当地日期。",
            "- 由 `tools/watch.py` 生成，规则和来源见 [A 股成交额专题](../ashare/REPORT.md)。"]
    row = {"close": round(P[-1], 2), "chg": round(chg(n - 1), 2), "amt": round(A[-1]), "a5": round(a5), "f5": round(f5),
           "margin": round(m_v) if m_d else None, "ust": u_v, "pos": pos, "neg": neg, "total": len(sig), "complete": complete}
    return T, "\n".join(out) + "\n", row


def write_index(hist):
    out = ["# A 股信号日报", "",
           "每个工作日早上由 `tools/watch.py` 自动生成，覆盖上一个交易日的数据。信号和规则来自 [A 股成交额专题](../ashare/REPORT.md)；"
           "只是数据整理，不是预测，也不构成投资建议。", "",
           "| 日期 | 中证全指 | 涨跌 | 成交额（亿元） | ETF 5 日净流入（亿元） | 融资余额（亿元） | 10 年期美债（%） | 积极 / 偏弱 | 报告 |",
           "|---|---|---|---|---|---|---|---|---|"]
    for d in sorted(hist, reverse=True):
        h = hist[d]
        out.append(f"| {d} | {h['close']:,.0f} | {h['chg']:+.2f}% | {h['amt']:,} | {h['f5']:+,} | "
                   f"{'—' if h['margin'] is None else format(h['margin'], ',')} | {'—' if h['ust'] is None else h['ust']} | "
                   f"{h['pos']} / {h['neg']} | [signals_{d}.md](signals_{d}.md) |")
    open(os.path.join(OUT, "README.md"), "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")


def main():
    hpath = os.path.join(OUT, "history.json")
    hist = json.load(open(hpath, encoding="utf-8")) if os.path.exists(hpath) else {}
    for attempt in range(args.retry + 1):
        T, md, row = build(*fetch())
        if not args.force and T in hist and hist[T]["complete"]:
            log(f"{T} 的报告已存在且数据齐全，跳过")
            return
        if row["complete"] or attempt == args.retry:
            break
        log(f"{T} 的两融或 ETF 份额还没公布，{args.wait} 秒后重试（第 {attempt + 1} 次）")
        time.sleep(args.wait)
    open(os.path.join(OUT, f"signals_{T}.md"), "w", encoding="utf-8", newline="\n").write(md)
    hist[T] = row
    json.dump(hist, open(hpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    write_index(hist)
    log(f"已生成 signals_{T}.md（数据{'齐全' if row['complete'] else '不全'}；积极 {row['pos']}、偏弱 {row['neg']}）")


try:
    main()
except Exception:
    log("出错：\n" + traceback.format_exc())
    sys.exit(1)
