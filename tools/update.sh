#!/usr/bin/env bash
# 一键更新：下载数据 → 复刻二级债基指数 → 验证 2 回测 → 采样 → 生成页面 → 回填分析文档和验证文档里的数字并复核结论
# One-shot update: fetch → replicate bond-fund index → sample → build pages → refill ANALYSIS.md / VERIFY.md and re-check conclusions
# 用法 | usage: tools/update.sh [--no-fetch] [--no-funds]
#   --no-fetch  不下载任何数据，全部用 raw/ 里已有的
#   --no-funds  下载 FRED、Yahoo、中证数据，但不重新下载约 900 只二级债基的净值（最慢的一步，几分钟）
set -euo pipefail
export PYTHONIOENCODING=utf-8
cd "$(dirname "$0")/.."
DOC="docs/ANALYSIS.md"
VERIFY="docs/VERIFY.md"
FETCH=1; FUNDS=1
for a in "$@"; do
  case "$a" in
    --no-fetch) FETCH=0; FUNDS=0 ;;
    --no-funds) FUNDS=0 ;;
    *) echo "未知参数：$a" >&2; exit 2 ;;
  esac
done

# 找一个装了 numpy 的 Python；可用环境变量 PYTHON 指定 | pick a Python with numpy, or set $PYTHON
if [ -z "${PYTHON:-}" ]; then
  for c in python3 python; do
    if command -v "$c" >/dev/null && "$c" -c "import numpy" >/dev/null 2>&1; then PYTHON="$c"; break; fi
  done
fi
[ -n "${PYTHON:-}" ] || { echo "找不到装有 numpy 的 Python，请先 pip install -r requirements.txt，或设置 PYTHON=..." >&2; exit 1; }
export PYTHON

[ "$FETCH" = 1 ] && bash tools/fetch.sh
[ "$FETCH" = 1 ] && "$PYTHON" -I tools/fetch_cn.py raw   # 国内数据（B、C 部分）
[ "$FUNDS" = 1 ] && "$PYTHON" -I tools/fetch_funds.py raw build
[ -d raw/funds ] || { echo "raw/funds 里没有基金净值，请先不带 --no-funds 运行一次" >&2; exit 1; }
"$PYTHON" -I tools/replica.py raw/funds build/bondfund.json
"$PYTHON" -I tools/verify2.py raw "$VERIFY" build/verify2.json   # 验证 2：回测、回填 VERIFY.md、输出页面数据
"$PYTHON" -I tools/sample.py raw build/bondfund.json > build/data.json
# 两个页面模板共用 tools/common.js，构建时内联，生成的页面仍是单个自包含文件
"$PYTHON" -I - tools/common.js build/data.json docs tools/template.html=index.html tools/template_mobile.html=mobile.html <<'PY'
import sys
common, data, outdir = sys.argv[1:4]
c, d = open(common, encoding="utf-8").read(), open(data).read()
assert "__DATA__" not in c
for pair in sys.argv[4:]:
    tpl, name = pair.split("=")
    t = open(tpl, encoding="utf-8").read()
    assert t.count("__DATA__") == 1 and t.count("/*__COMMON__*/") == 1, tpl
    open(f"{outdir}/{name}", "w", encoding="utf-8", newline="\n").write(t.replace("/*__COMMON__*/", c, 1).replace("__DATA__", d, 1))
    print(f"页面已生成：{outdir}/{name}")
PY
"$PYTHON" -I tools/report.py raw build/data.json "$DOC"
"$PYTHON" -I tools/analysis_cn.py raw "$DOC" build/cn.json   # B、C 部分，同时输出分析报告页的图表数据
"$PYTHON" -I tools/verify_report.py raw build/bondfund.json "$VERIFY"
# 独立的报告页：专题验证报告、分析报告（Markdown 转 HTML + 交互图表）
"$PYTHON" -I tools/build_report.py verify "$VERIFY" build/data.json tools/template_verify.html docs/verify/index.html tools/common.js
"$PYTHON" -I tools/build_report.py analysis "$DOC" build/cn.json tools/template_analysis.html docs/analysis/index.html
