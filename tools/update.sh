#!/usr/bin/env bash
# 一键更新：下载数据 → 15 天采样 → 生成页面 → 回填分析文档里的数字并复核结论
# One-shot update: fetch → sample → build page → refill numbers in docs/ANALYSIS.md and re-check conclusions
# 用法 | usage: tools/update.sh [--no-fetch]   （--no-fetch 用 raw/ 里已有的数据）
set -euo pipefail
export PYTHONIOENCODING=utf-8
cd "$(dirname "$0")/.."
DOC="docs/ANALYSIS.md"

# 找一个装了 numpy 的 Python；可用环境变量 PYTHON 指定 | pick a Python with numpy, or set $PYTHON
if [ -z "${PYTHON:-}" ]; then
  for c in python3 python; do
    if command -v "$c" >/dev/null && "$c" -c "import numpy" >/dev/null 2>&1; then PYTHON="$c"; break; fi
  done
fi
[ -n "${PYTHON:-}" ] || { echo "找不到装有 numpy 的 Python，请先 pip install -r requirements.txt，或设置 PYTHON=..." >&2; exit 1; }
export PYTHON

[ "${1:-}" = "--no-fetch" ] || bash tools/fetch.sh
"$PYTHON" -I tools/sample.py raw > build/data.json
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
