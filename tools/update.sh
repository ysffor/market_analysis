#!/usr/bin/env bash
# 一键更新：下载数据 → 15 天采样 → 生成页面 → 回填分析文档里的数字并复核结论
# One-shot update: fetch → sample → build page → refill numbers in docs/ANALYSIS.md and re-check conclusions
# 用法 | usage: tools/update.sh [--no-fetch]   （--no-fetch 用 raw/ 里已有的数据）
set -euo pipefail
export PYTHONIOENCODING=utf-8
cd "$(dirname "$0")/.."
PAGE="docs/index.html"
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
"$PYTHON" -I - tools/template.html build/data.json "$PAGE" <<'PY'
import sys
tpl, data, out = sys.argv[1:4]
t = open(tpl, encoding="utf-8").read()
assert t.count("__DATA__") == 1
open(out, "w", encoding="utf-8", newline="\n").write(t.replace("__DATA__", open(data).read()))
PY
echo "页面已生成：$PAGE"
"$PYTHON" -I tools/report.py raw build/data.json "$DOC"
