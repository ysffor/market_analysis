# 美元流动性观察：黄金 · 原油 · 美债收益率

一个静态网页加两份文档，内容分两类：

- **分析**：分三部分：A 美元流动性的趋势（含黄金、原油、10 年期美债收益率与美元流动性的关系），B 人民币流动性的趋势，C 美元收紧对人民币流动性的影响有多大。
- **专题验证**：用数据检验市场上流传的说法，和上面的分析相互独立。

**在线查看：** 电脑版 <https://ysffor.github.io/market_analysis/> ｜ 手机版 <https://ysffor.github.io/market_analysis/mobile.html> ｜ 分析报告 <https://ysffor.github.io/market_analysis/analysis/> ｜ 专题验证报告 <https://ysffor.github.io/market_analysis/verify/> ｜ A 股成交额专题 <https://ysffor.github.io/market_analysis/ashare/>

- **页面**：电脑版 `docs/index.html` 和手机版 `docs/mobile.html`。每个都是单个 HTML 文件，数据内嵌，打开不需要联网，也不依赖任何外部库。
- **专题验证报告**（`docs/verify/index.html`）：把验证文档做成独立网页，正文中嵌入交互图表，电脑和手机共用。
- **分析文档**（[docs/ANALYSIS.md](docs/ANALYSIS.md)）：A / B / C 三部分的分析思路、方法、主要发现、判断流程和局限。目前看板页面只展示 A 部分；B、C 部分的结果在文档和分析报告页（`docs/analysis/index.html`，带交互图表）里。
- **验证文档**（[docs/VERIFY.md](docs/VERIFY.md)）：每条验证的说法、结论、方法与数据、结果和局限。
- **A 股成交额专题**（[docs/ashare/REPORT.md](docs/ashare/REPORT.md)，网页版 `docs/ashare/index.html`）：A 股成交额腰斩的原因拆解（行情回落、杠杆资金、宽基 ETF 资金进出、IPO、资金面、政策事件），独立于上面两份文档。

这些文档里的数字都由脚本自动计算回填，每次更新还会复核结论是否仍然成立。

## 页面内容

| 分类 | 图 | 说明 |
|---|---|---|
| 分析 | 三者走势对比 | 黄金、WTI 原油、10 年期美债收益率，每 15 天一个采样点；以区间起点 = 100 指数化，放在同一纵轴比较涨跌幅；可切换对数或线性刻度 |
| 分析 | 价格层 vs 数量层 | 共用时间轴的三幅分面图：实际利率与名义收益率、美元指数、美联储净流动性；阴影标出 QE 和 QT 时期 |
| 分析 | 拆解 | 实际利率 = 名义 − 通胀预期；净流动性 = 总资产 − TGA − 逆回购；看每次变化来自哪一项 |
| 分析 | 领先滞后 | 净流动性和实际利率的变化在不同时间错位下的相关系数，附粗略显著性门槛 |
| 专题验证 | 验证 1：沪深300全收益跌破二级债基指数，就是底部？ | 两条线叠加和两者的比值，可切换基准日和二级债基口径（按 885007 校正的三种情景 / 未校正），标出跌破点（实时信号日）和历次大底 |
| 专题验证 | 验证 2：红利指数按 MA120 均线定投、止盈，有没有用？ | 7 个红利指数的价格、均线与偏离度，可切换 120 日 / 120 周均线，附各版本的回测结果表 |

分析类的图都支持 20 / 10 / 5 / 3 / 1 年区间切换；专题验证板块在页面底部单独成区，不受区间切换影响。所有图都支持悬停读数和亮色、暗色模式，页面底部有完整数据表。

手机版的图和电脑版相同，只是针对窄屏重新排版：读数固定显示在每张图上方，在图上点按或左右拖动即可更新，默认显示最新一个采样点。电脑版在窄屏上打开时，会提示切换到手机版。

## 快速开始

依赖：bash、curl、Python 3 和 numpy。Windows 上请用 Git Bash 运行。

```bash
pip install -r requirements.txt
bash tools/update.sh        # 下载数据 → 生成两个页面 → 更新 ANALYSIS.md 和 VERIFY.md 里的数字（约 7 分钟）
```

然后用浏览器打开 `docs/index.html`（电脑版）或 `docs/mobile.html`（手机版）。

最慢的一步是下载约 900 只二级债基的净值。只想更新分析部分时用 `bash tools/update.sh --no-funds`（沿用上次的基金净值）；完全不下载、只重新生成时用 `--no-fetch`。

## 目录结构

```
├── README.md
├── requirements.txt
├── docs/
│   ├── ANALYSIS.md      分析文档（AUTO 区块由脚本生成）
│   ├── VERIFY.md        专题验证文档（AUTO 区块由脚本生成）
│   ├── index.html       生成的电脑版页面（GitHub Pages 首页）
│   ├── mobile.html      生成的手机版页面
│   ├── verify/index.html  生成的专题验证报告页
│   ├── analysis/index.html  生成的分析报告页
│   ├── ashare/REPORT.md  A 股成交额专题文档（AUTO 区块由脚本生成）
│   ├── ashare/index.html  生成的 A 股成交额专题报告页
│   └── .nojekyll
├── tools/
│   ├── update.sh        一键更新
│   ├── fetch.sh         下载原始数据（FRED、Yahoo、中证）
│   ├── fetch_cn.py      下载国内数据（中国货币网、东方财富），用于分析 B、C 部分
│   ├── fetch_ashare.py  下载 A 股成交额专题的数据（中证全指、两融、IPO、上交所宽基 ETF 份额与价格）
│   ├── fetch_funds.py   下载全部二级债基的净值（专题验证用）
│   ├── replica.py       按万得 885007 规则复刻二级债基指数，并按公开点位校正
│   ├── sample.py        每 15 天采样，输出页面数据
│   ├── template.html    电脑版页面模板
│   ├── template_mobile.html  手机版页面模板
│   ├── template_verify.html  专题验证报告页模板
│   ├── template_analysis.html  分析报告页模板
│   ├── template_ashare.html  A 股成交额专题报告页模板
│   ├── common.js        两个页面共用的数据处理与分析逻辑（构建时内联）
│   ├── report.py        计算分析文档 A 部分的数字、复核结论、维护事件列表
│   ├── analysis_cn.py   计算分析文档 B、C 部分：人民币流动性与美元传导
│   ├── verify_report.py 验证 1：计算验证文档里的数字、复核结论
│   ├── verify2.py       验证 2：回测红利指数均线策略、回填验证文档、输出页面数据
│   ├── ashare.py        A 股成交额专题：分解、量价弹性、杠杆、宽基 ETF、IPO、事件，回填专题文档
│   └── build_report.py  把 VERIFY.md、ANALYSIS.md、ashare/REPORT.md 转成独立的报告页，并嵌入交互图表
├── raw/                 下载的原始数据（不进 git）
└── build/               中间数据（不进 git）
```

修改页面请改模板，不要直接改生成的 `docs/*.html`。分析逻辑、图表配置、QE/QT 时期等两个页面共用的内容在 `tools/common.js` 里，只改一处；排版和交互分别在 `template.html` 和 `template_mobile.html` 里。文档的维护约定见 [ANALYSIS.md 第 10 节](docs/ANALYSIS.md#10-更新与维护)。

## 数据来源

| 指标 | 来源 |
|---|---|
| 10 年期名义收益率、实际利率、通胀预期 | FRED：`DGS10`、`DFII10`、`T10YIE` |
| WTI 原油 | FRED：`DCOILWTICO` |
| 美元指数（广义贸易加权） | FRED：`DTWEXBGS` |
| 美联储总资产、TGA、逆回购 | FRED：`WALCL`、`WTREGEN`、`RRPONTSYD` |
| 黄金 | Yahoo Finance，COMEX 黄金期货 `GC=F` |
| 沪深300全收益（专题验证） | 中证指数官网，`H00300` |
| 二级债基指数（专题验证） | 天天基金上全部二级债基的历史净值，按万得 885007 的规则复刻，再用 885007 的公开点位和年度收益校正（方法见 VERIFY.md） |
| 红利指数（专题验证 2） | 中证指数官网：中证红利、红利低波、红利低波100、央企红利、国企红利、上证红利、港股通高股息的价格指数和全收益指数 |
| 货币基金指数（专题验证 2） | 中证指数官网，`H11025`，用于计算卖出后现金的收益 |
| 联邦基金利率、美元兑人民币（分析 B、C） | FRED：`DFF`、`DEXCHUS` |
| 回购定盘利率 FR007 / DR007、SHIBOR（分析 B、C） | 中国货币网（全国银行间同业拆借中心） |
| 中美国债收益率、M2/M1、新增人民币贷款、外汇储备、存款准备金率、LPR、PMI、CPI（分析 B、C） | 东方财富数据中心（原始来源为人民银行、外汇局、统计局等） |
| A 股成交额、中证全指（A 股专题） | 中证指数官网，`000985` |
| 两融余额与交易额、新股发行净募资（A 股专题） | 东方财富数据中心 |
| 宽基 ETF 份额（A 股专题） | 上海证券交易所，9 只主要宽基 ETF 每周份额；周收盘价来自东方财富 |

## 数据许可

两个页面内嵌了采样后的数据（分析部分每 15 天一个点，专题验证部分每周一个点），随仓库公开发布到 GitHub Pages。原始下载数据（`raw/`）和中间数据（`build/`）不进 git，由使用者运行脚本时自行下载。

- FRED 上的序列大多来自美国政府机构，通常可以自由使用，具体以 FRED 上每个序列标注的说明为准。
- 沪深300全收益来自中证指数官网，二级债基复刻指数由公开披露的基金净值计算，页面只内嵌按周抽样的指数点位。
- 黄金价格来自 Yahoo Finance，它的服务条款对转载数据有限制。如果你 fork 本项目并公开发布，请自行确认数据使用条款，或者在 `tools/fetch.sh` 和 `tools/sample.py` 里换成别的黄金数据源。

## 发布到 GitHub Pages

页面放在 `docs/` 目录，`docs/.nojekyll` 让 GitHub 原样发布，不经过 Jekyll 处理。在仓库的 Settings → Pages 里，把 Source 设为 "Deploy from a branch"，分支选 `main`，目录选 `/docs`。

更新数据后，重新运行 `bash tools/update.sh`，提交 `docs/` 下的改动并推送即可。

## 免责声明

本项目只用于学习和研究，不构成任何投资建议。分析结论基于历史相关性，相关不等于因果，详见 [ANALYSIS.md 第 9 节](docs/ANALYSIS.md#9-局限) 和 [VERIFY.md](docs/VERIFY.md) 中每条验证的局限。
