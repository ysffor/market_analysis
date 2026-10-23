#!/usr/bin/env bash
# 下载原始数据到 raw/（只放下载文件，不放脚本）：FRED 各序列 CSV + Yahoo 黄金期货日线
# Download raw data into raw/ (downloads only): FRED series CSVs + Yahoo gold futures daily bars
set -euo pipefail
RAW="$(cd "$(dirname "$0")/../raw" && pwd)"
START="$(( $(date +%Y) - 21 ))-01-01"   # 多取一年，保证 20 年窗口起点之前有值
FRED="DGS10 DFII10 T10YIE DCOILWTICO DTWEXBGS WALCL WTREGEN RRPONTSYD"
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
