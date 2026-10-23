# 美元流动性观察：黄金 · 原油 · 美债收益率

一个静态网页加一份分析文档，用来观察过去 20 年黄金、原油、10 年期美债收益率的走势，以及它们和美元流动性的关系。

**在线查看：** 电脑版 <https://ysffor.github.io/market_analysis/> ｜ 手机版 <https://ysffor.github.io/market_analysis/mobile.html>

- **页面**：电脑版 `docs/index.html` 和手机版 `docs/mobile.html`。每个都是单个 HTML 文件，数据内嵌，打开不需要联网，也不依赖任何外部库。
- **分析文档**（[docs/ANALYSIS.md](docs/ANALYSIS.md)）：分析思路、主要发现、判断流程和局限。文档里的数字由脚本自动计算回填，每次更新还会复核结论是否仍然成立。

## 页面内容

| 图 | 说明 |
|---|---|
| 三者走势对比 | 黄金、WTI 原油、10 年期美债收益率，每 15 天一个采样点；以区间起点 = 100 指数化，放在同一纵轴比较涨跌幅；可切换对数或线性刻度 |
| 价格层 vs 数量层 | 共用时间轴的三幅分面图：实际利率与名义收益率、美元指数、美联储净流动性；阴影标出 QE 和 QT 时期 |
| 拆解 | 实际利率 = 名义 − 通胀预期；净流动性 = 总资产 − TGA − 逆回购；看每次变化来自哪一项 |
| 领先滞后 | 净流动性和实际利率的变化在不同时间错位下的相关系数，附粗略显著性门槛 |

所有图都支持 20 / 10 / 5 / 3 / 1 年区间切换和悬停读数，支持亮色和暗色模式，底部有完整数据表。

手机版的图和电脑版相同，只是针对窄屏重新排版：读数固定显示在每张图上方，在图上点按或左右拖动即可更新，默认显示最新一个采样点。电脑版在窄屏上打开时，会提示切换到手机版。

## 快速开始

依赖：bash、curl、Python 3 和 numpy。Windows 上请用 Git Bash 运行。

```bash
pip install -r requirements.txt
bash tools/update.sh        # 下载数据 → 生成 docs/index.html → 更新 docs/ANALYSIS.md 里的数字
```

然后用浏览器打开 `docs/index.html`（电脑版）或 `docs/mobile.html`（手机版）。

已经下载过数据、只想重新生成时，用 `bash tools/update.sh --no-fetch`。

## 目录结构

```
├── README.md
├── requirements.txt
├── docs/
│   ├── ANALYSIS.md      分析文档（AUTO 区块由脚本生成）
│   ├── index.html       生成的电脑版页面（GitHub Pages 首页）
│   ├── mobile.html      生成的手机版页面
│   └── .nojekyll
├── tools/
│   ├── update.sh        一键更新
│   ├── fetch.sh         下载原始数据
│   ├── sample.py        每 15 天采样，输出页面数据
│   ├── template.html    电脑版页面模板
│   ├── template_mobile.html  手机版页面模板
│   ├── common.js        两个页面共用的数据处理与分析逻辑（构建时内联）
│   └── report.py        计算文档里的数字、复核结论、维护事件列表
├── raw/                 下载的原始数据（不进 git）
└── build/               中间数据（不进 git）
```

修改页面请改模板，不要直接改生成的 `docs/*.html`。分析逻辑、图表配置、QE/QT 时期等两个页面共用的内容在 `tools/common.js` 里，只改一处；排版和交互分别在 `template.html` 和 `template_mobile.html` 里。文档的维护约定见 [ANALYSIS.md 第 8 节](docs/ANALYSIS.md#8-更新与维护)。

## 数据来源

| 指标 | 来源 |
|---|---|
| 10 年期名义收益率、实际利率、通胀预期 | FRED：`DGS10`、`DFII10`、`T10YIE` |
| WTI 原油 | FRED：`DCOILWTICO` |
| 美元指数（广义贸易加权） | FRED：`DTWEXBGS` |
| 美联储总资产、TGA、逆回购 | FRED：`WALCL`、`WTREGEN`、`RRPONTSYD` |
| 黄金 | Yahoo Finance，COMEX 黄金期货 `GC=F` |

## 数据许可

`docs/index.html` 内嵌了每 15 天采样一次的数据，随仓库公开发布到 GitHub Pages。原始下载数据（`raw/`）和中间数据（`build/`）不进 git，由使用者运行脚本时自行下载。

- FRED 上的序列大多来自美国政府机构，通常可以自由使用，具体以 FRED 上每个序列标注的说明为准。
- 黄金价格来自 Yahoo Finance，它的服务条款对转载数据有限制。如果你 fork 本项目并公开发布，请自行确认数据使用条款，或者在 `tools/fetch.sh` 和 `tools/sample.py` 里换成别的黄金数据源。

## 发布到 GitHub Pages

页面放在 `docs/` 目录，`docs/.nojekyll` 让 GitHub 原样发布，不经过 Jekyll 处理。在仓库的 Settings → Pages 里，把 Source 设为 "Deploy from a branch"，分支选 `main`，目录选 `/docs`。

更新数据后，重新运行 `bash tools/update.sh`，提交 `docs/` 下的改动并推送即可。

## 免责声明

本项目只用于学习和研究，不构成任何投资建议。分析结论基于历史相关性，相关不等于因果，详见 [ANALYSIS.md 第 7 节](docs/ANALYSIS.md#7-局限)。
