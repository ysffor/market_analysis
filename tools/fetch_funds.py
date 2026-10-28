# 专题验证用：下载天天基金的全部二级债基（"债券型-混合二级"）列表和历史净值到 raw/funds/
# 同一基金的多个份额只取一个：优先 A 类、A/B 或无后缀的份额（成立最早），避免取到后来新增的 C 类。约 900 只基金，几分钟。
# For the verification section: download all secondary bond funds' NAV histories from Eastmoney into raw/funds/
# 用法 | usage: python -I fetch_funds.py <raw 目录> <build 目录>
import json, os, re, sys, time, urllib.request

RAW, BUILD = sys.argv[1], sys.argv[2]
HDR = {"User-Agent": "Mozilla/5.0", "Referer": "https://fund.eastmoney.com/"}


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=60).read()


lst = get("https://fund.eastmoney.com/js/fundcode_search.js").decode("utf-8-sig")
rows = json.loads(lst[lst.index("["):lst.rindex("]") + 1])
groups = {}
for code, _, name, typ, _ in rows:
    if typ != "债券型-混合二级":
        continue
    n = name.strip()
    base = re.sub(r"(A/B|[A-Z])$|[A-Z]类$|\(.*\)$|（.*）$", "", n)
    groups.setdefault(base, []).append((0 if re.search(r"(A|A/B)$|[^A-Z]$", n) else 1, code, n))
keep = sorted(min(v)[1:] for v in groups.values())
if len(keep) < 300:
    sys.exit(f"二级债基只找到 {len(keep)} 只，列表格式可能变了")
os.makedirs(BUILD, exist_ok=True)
with open(f"{BUILD}/funds.tsv", "w", encoding="utf-8") as f:
    for c, n in keep:
        f.write(f"{c}\t{n}\n")

out = f"{RAW}/funds"
os.makedirs(out, exist_ok=True)
fail = 0
for i, (c, _) in enumerate(keep):
    try:
        data = get(f"https://fund.eastmoney.com/pingzhongdata/{c}.js")
        if b"Data_netWorthTrend" in data:
            open(f"{out}/{c}.js", "wb").write(data)
        else:
            fail += 1
    except Exception as e:  # 单只失败不影响整体；沿用上次下载的文件
        fail += 1
        print(f"基金 {c} 下载失败：{e}", file=sys.stderr)
    time.sleep(0.15)
    if i % 200 == 0:
        print(f"基金净值 {i}/{len(keep)}", flush=True)
print(f"二级债基 {len(keep)} 只，下载失败 {fail} 只")
if fail > len(keep) * 0.1:
    sys.exit("失败超过 10%，请稍后重试")
