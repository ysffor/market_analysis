# 生成独立的报告页：把 Markdown 文档转成 HTML，并在指定位置插入交互图表。
#   verify   docs/VERIFY.md   → docs/verify/index.html：每条验证的"方法与数据"之前插入验证图表（复用 tools/common.js）
#   analysis docs/ANALYSIS.md → docs/analysis/index.html：A 部分放看板链接，B、C 部分插入月度图表（绘图代码在模板里）
# Markdown 转换只覆盖这两份文档用到的语法（标题、段落、列表、表格、引用、代码块、粗体、行内代码、链接），不引入额外依赖。
# 面向维护者的章节（VERIFY.md 的"维护"、ANALYSIS.md 的"更新与维护"）不放进报告；指向报告里不存在的章节的链接改指向 GitHub 原文。
# Build the standalone report pages from VERIFY.md / ANALYSIS.md with interactive charts inserted.
# 用法 | usage:
#   python -I build_report.py verify   <VERIFY.md>   <build/data.json> <template_verify.html>   <输出> <common.js>
#   python -I build_report.py analysis <ANALYSIS.md> <build/cn.json>   <template_analysis.html> <输出>
import html, json, os, re, sys

MODE, SRC, DATA_JSON, TPL, OUT = sys.argv[1:6]
COMMON = sys.argv[6] if len(sys.argv) > 6 else None
REPO = "https://github.com/ysffor/market_analysis/blob/main/docs/"
SELF = {"verify": "VERIFY.md", "analysis": "ANALYSIS.md"}[MODE]
OTHER = {"verify": ("ANALYSIS.md", "../analysis/index.html"), "analysis": ("VERIFY.md", "../verify/index.html")}[MODE]

CARDS = {
    "1": """<div class="card" id="verify">
  <p class="card-cap">交互图表：可切换基准日和二级债基口径，点按或悬停查看数值。页面按周数据计算，和下文按日数据算的日期可能差几天。</p>
  <p class="verdict" id="v1-verdict"></p>
  <div class="vbar"><span class="seg-label">基准日（两者在这天都设为 1000）</span><span class="seg" id="v1-base"></span></div>
  <div class="vbar"><span class="seg-label">二级债基口径（默认情景 A）</span><span class="seg" id="v1-scen"></span></div>
  <div class="vlegend">
    <span><i style="background:var(--s-csi)"></i>沪深300全收益</span>
    <span><i style="background:var(--text-secondary)"></i><span id="v1-bf-legend">二级债基指数</span></span>
    <span><i style="background:var(--text-primary)"></i>比值</span>
    <span>▼ 跌破点（实时信号日）　○ 历次大底</span>
  </div>
  <div class="readout" id="v1-ro"></div>
  <svg id="v1" tabindex="0" role="img" aria-label="沪深300全收益与二级债基指数叠加图及两者比值"></svg>
  <p class="reading" id="v1-sum"></p>
  <a id="v1-doc" hidden></a>
</div>""",
    "2": """<div class="card" id="verify2">
  <p class="card-cap">交互图表：可切换指数和均线类型，点按或悬停查看数值；表中为该指数的回测结果（按日数据）。</p>
  <p class="verdict" id="v2-verdict"></p>
  <div class="vbar"><span class="seg-label">指数</span><select id="v2-idx" class="v2sel" aria-label="选择红利指数"></select>
    <span class="seg-label">MA120 指</span><span class="seg" id="v2-mode"></span></div>
  <div class="vlegend">
    <span><i style="background:var(--text-primary)"></i>价格指数</span>
    <span><i style="background:var(--text-secondary)"></i>均线（虚线）</span>
    <span><i style="background:var(--s-oil)"></i>偏离度</span>
  </div>
  <div class="readout" id="v2-ro"></div>
  <svg id="v2" tabindex="0" role="img" aria-label="红利指数价格、均线与偏离度"></svg>
  <div class="v2tbl"><table id="v2-table"></table></div>
  <p class="reading" id="v2-sum"></p>
  <a id="v2-doc" hidden></a>
</div>""",
    "A": """<div class="card note-card">A 部分的交互图表（黄金、原油、美债走势，价格层与数量层，拆解，领先滞后）在看板上：
<a href="../index.html">电脑版</a> · <a href="../mobile.html">手机版</a>。</div>""",
    "cb": """<div class="card"><p class="card-cap">交互图表：人民币流动性的主要指标（月度）。阴影为美元收紧期（加息期或美元走强期，见第 6.3 节）；点按或悬停查看数值。</p>
  <div class="readout" id="cb-ro"></div><svg id="cb" tabindex="0" role="img" aria-label="人民币利率、货币增速、新增贷款与央行工具"></svg></div>""",
    "ci": """<div class="card"><p class="card-cap">交互图表：美元与人民币的收紧指数（月度，数值越大越紧）。阴影为美元收紧期；点按或悬停查看数值。</p>
  <div class="readout" id="ci-ro"></div><svg id="ci" tabindex="0" role="img" aria-label="美元与人民币价格层、数量层收紧指数"></svg></div>""",
    "cc": """<div class="card"><p class="card-cap">交互图表：传导渠道（月度）。阴影为美元收紧期；点按或悬停查看数值。</p>
  <div class="readout" id="cc-ro"></div><svg id="cc" tabindex="0" role="img" aria-label="中美国债收益率、利差、美元兑人民币与外汇储备"></svg></div>""",
}
# analysis 模式：在这些标题之前插入对应的卡片
ANALYSIS_INSERT = {"### 4.1 发现 1：三者反映的是美元的价格，不是数量": "A", "### 5.3 发现": "cb",
                   "### 6.1 整体解释力": "ci", "### 6.3 事件研究": "cc"}

SEEN = {}


def slug(text):
    """与 GitHub 相同的标题锚点：转小写，去掉标点（保留文字、数字、连字符和空格），空格换成连字符；重名时依次加 -1、-2"""
    s = re.sub(r"[^\w\- ]", "", text.lower()).replace(" ", "-")
    k = SEEN.get(s, 0)
    SEEN[s] = k + 1
    return s if k == 0 else f"{s}-{k}"


def link_url(u):
    if u.startswith(("http://", "https://", "#")):
        return u
    if u.startswith(SELF):
        return u[len(SELF):] or "#"
    if u.startswith(OTHER[0]):
        return OTHER[1] + u[len(OTHER[0]):]       # 另一份文档有自己的报告页
    if u.startswith("../"):
        return u
    return REPO + u


def inline(s):
    codes = []
    s = re.sub(r"`([^`]+)`", lambda m: codes.append(m.group(1)) or f"\x00{len(codes)-1}\x00", s)
    s = s.replace("\\*", "\x01")          # Markdown 转义的星号（如显著性标记的说明），最后还原成 *
    s = html.escape(s, quote=False)
    s = re.sub(r"&lt;(https?://[^&\s]+)&gt;", lambda m: f'<a href="{m.group(1)}">{m.group(1)}</a>', s)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: f'<a href="{html.escape(link_url(m.group(2)))}">{m.group(1)}</a>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = s.replace("\x01", "*")
    return re.sub(r"\x00(\d+)\x00", lambda m: f"<code>{html.escape(codes[int(m.group(1))], quote=False)}</code>", s)


LIST_RE = re.compile(r"^(\s*)([-*]|\d+\.)\s+")


def table(rows):
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    head, body = cells[0], cells[2:]
    out = ['<div class="tbl"><table><thead><tr>'] + [f"<th>{inline(c)}</th>" for c in head] + ["</tr></thead><tbody>"]
    for r in body:
        out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
    return "".join(out) + "</tbody></table></div>"


def unwrap(h):
    """列表项只有一段文字时去掉外层 <p>，让列表更紧凑"""
    return h[3:-4] if h.startswith("<p>") and h.endswith("</p>") and h.count("<p>") == 1 else h


def blocks(lines):
    out, i, n = [], 0, len(lines)

    def starts_block(l):
        s = l.strip()
        return (not s or s.startswith(("#", ">", "|", "<!--", "@@CARD", "```")) or s == "---" or LIST_RE.match(l))

    while i < n:
        line, s = lines[i], lines[i].strip()
        if not s:
            i += 1
        elif s.startswith("```"):
            code = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            out.append("<pre><code>" + html.escape("\n".join(code), quote=False) + "</code></pre>")
        elif s.startswith("<!--"):
            while i < n and "-->" not in lines[i]:
                i += 1
            i += 1
        elif s.startswith("@@CARD"):
            out.append(CARDS[s[6:-2]])
            i += 1
        elif s.startswith("#"):
            level = len(s) - len(s.lstrip("#"))
            text = s[level:].strip()
            out.append(f'<h{level} id="{html.escape(slug(text))}">{inline(text)}</h{level}>')
            i += 1
        elif s == "---":
            out.append("<hr>")
            i += 1
        elif s.startswith(">"):
            q = []
            while i < n and lines[i].strip().startswith(">"):
                q.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append("<blockquote>" + blocks(q) + "</blockquote>")
        elif s.startswith("|"):
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(lines[i])
                i += 1
            out.append(table(rows))
        elif LIST_RE.match(line):
            m = LIST_RE.match(line)
            indent, ordered = len(m.group(1)), m.group(2)[0].isdigit()
            items = []
            while i < n:
                m = LIST_RE.match(lines[i])
                if not m or len(m.group(1)) != indent or m.group(2)[0].isdigit() != ordered:
                    break
                c = len(m.group(0))
                body = [lines[i][c:]]
                i += 1
                while i < n:
                    l = lines[i]
                    if l.strip() and len(l) - len(l.lstrip()) <= indent:
                        break
                    if not l.strip():               # 空行：后面还有缩进内容才算同一项
                        j = i
                        while j < n and not lines[j].strip():
                            j += 1
                        if j >= n or len(lines[j]) - len(lines[j].lstrip()) <= indent:
                            break
                    body.append(l[min(c, len(l) - len(l.lstrip())):] if l.strip() else "")
                    i += 1
                items.append(body)
            tag = "ol" if ordered else "ul"
            start = f' start="{m0}"' if ordered and (m0 := int(LIST_RE.match(line).group(2)[:-1])) != 1 else ""
            out.append(f"<{tag}{start}>" + "".join(f"<li>{unwrap(blocks(b))}</li>" for b in items) + f"</{tag}>")
        else:
            para = []
            while i < n and not starts_block(lines[i]):
                para.append(lines[i].strip())
                i += 1
            if not para:            # 不应发生：防止死循环
                para.append(s)
                i += 1
            out.append(f"<p>{inline(' '.join(para))}</p>")
    return "\n".join(out)


# 读入文档：去掉面向维护者的章节，按模式插入图表卡片
src, lines, cur, skip = open(SRC, encoding="utf-8").read().splitlines(), [], None, False
for l in src:
    if l.startswith("## "):
        skip = l.strip() in ("## 维护",) or bool(re.match(r"## \d+\. 更新与维护", l.strip()))
        m = re.match(r"## 验证 (\d+)", l)
        cur = m.group(1) if m else None
    if skip:
        continue
    if MODE == "verify" and l.strip() == "### 方法与数据" and cur in CARDS:
        lines += [f"@@CARD{cur}@@", ""]
    if MODE == "analysis" and l.strip() in ANALYSIS_INSERT:
        lines += [f"@@CARD{ANALYSIS_INSERT[l.strip()]}@@", ""]
    lines.append(l)
report = blocks(lines)
need = {"verify": ('id="verify"', 'id="verify2"'), "analysis": ('id="cb"', 'id="ci"', 'id="cc"', "note-card")}[MODE]
assert all(k in report for k in need), "图表卡片没有全部插入，文档的结构可能变了"
# 报告里没有的锚点（例如被略去的"更新与维护"）改指向 GitHub 原文
ids = set(re.findall(r'id="([^"]+)"', report))
report = re.sub(r'href="#([^"]+)"', lambda m: m.group(0) if m.group(1) in ids else f'href="{REPO}{SELF}#{m.group(1)}"', report)

d = json.load(open(DATA_JSON, encoding="utf-8"))
data = {"dates": [], "verify": d["verify"], "verify2": d["verify2"]} if MODE == "verify" else d
t = open(TPL, encoding="utf-8").read()
assert t.count("__REPORT__") == 1 and t.count("__DATA__") == 1
if MODE == "verify":
    assert t.count("/*__COMMON__*/") == 1 and COMMON
    t = t.replace("/*__COMMON__*/", open(COMMON, encoding="utf-8").read(), 1)
t = t.replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")), 1)
t = t.replace("__REPORT__", report, 1)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, "w", encoding="utf-8", newline="\n").write(t)
print(f"报告页已生成：{OUT}")
