#!/usr/bin/env bash
# 下载原始数据到 raw/（只放下载文件，不放脚本）：FRED 各序列 CSV + Yahoo 黄金期货日线 + 中证沪深300全收益
# Download raw data into raw/ (downloads only): FRED series CSVs + Yahoo gold futures daily bars
set -euo pipefail
RAW="$(cd "$(dirname "$0")/../raw" && pwd)"
START="$(( $(date +%Y) - 21 ))-01-01"   # 多取一年，保证 20 年窗口起点之前有值
FRED="DGS10 DFII10 T10YIE DCOILWTICO DTWEXBGS WALCL WTREGEN RRPONTSYD DEXCHUS DFF"
for s in $FRED; do
  curl -fsSL -m 120 --retry 2 -o "$RAW/$s.csv.tmp" "https://fred.stlouisfed.org/graph/fredgraph.csv?id=$s&cosd=$START"
  head -1 "$RAW/$s.csv.tmp" | grep -q "observation_date,$s" || { echo "FRED $s: 返回内容不是 CSV" >&2; exit 1; }
  mv "$RAW/$s.csv.tmp" "$RAW/$s.csv"
  echo "FRED $s  $(tail -1 "$RAW/$s.csv")"
done
P1=$(date -d "$START" +%s 2>/dev/null || "${PYTHON:-python3}" -I -c "import datetime,sys;print(int(datetime.datetime.fromisoformat(sys.argv[1]).timestamp()))" "$START")
P2=$(( $(date +%s) + 86400 ))
curl -fsSL -m 120 --retry 2 -A "Mozilla/5.0" -o "$RAW/gold_yf.json.tmp" \
  "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?period1=$P1&period2=$P2&interval=1d"
grep -q '"timestamp"' "$RAW/gold_yf.json.tmp" || { echo "Yahoo GC=F: 返回内容没有行情数据" >&2; exit 1; }
mv "$RAW/gold_yf.json.tmp" "$RAW/gold_yf.json"
echo "Yahoo GC=F ok"

# 专题验证用：沪深300全收益指数（中证 H00300），从基日 2004-12-31 起
# For the verification section: CSI 300 Total Return index since its base date
curl -fsSL -m 120 --retry 2 -A "Mozilla/5.0" -o "$RAW/H00300.json.tmp" \
  "https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=H00300&startDate=20041231&endDate=$(date +%Y%m%d)"
grep -q '"tradeDate"' "$RAW/H00300.json.tmp" || { echo "中证 H00300: 返回内容没有行情数据" >&2; exit 1; }
mv "$RAW/H00300.json.tmp" "$RAW/H00300.json"
echo "CSI H00300 ok"

# 专题验证 2：红利指数（价格指数用来判断信号，全收益指数用来算收益）与中证货币基金指数（现金收益）
# Verification 2: dividend indices (price for signals, total return for performance) and the CSI money-fund index
for c in 000922 H00922 H30269 H20269 930955 H20955 000825 H00825 000824 H00824 000015 H00015 930914 H20914 H11025; do
  curl -fsSL -m 120 --retry 2 -A "Mozilla/5.0" -o "$RAW/$c.json.tmp" \
    "https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=$c&startDate=20040101&endDate=$(date +%Y%m%d)"
  grep -q '"tradeDate"' "$RAW/$c.json.tmp" || { echo "中证 $c: 返回内容没有行情数据" >&2; exit 1; }
  mv "$RAW/$c.json.tmp" "$RAW/$c.json"
done
echo "CSI dividend indices ok"
