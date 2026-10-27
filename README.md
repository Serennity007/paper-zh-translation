# paper-zh-translation

**[中文](README.md) | [English](README.en.md)**

![License](https://img.shields.io/badge/License-MIT-blue)
![Engine](https://img.shields.io/badge/engine-PyMuPDF-lightgrey)
![Python](https://img.shields.io/badge/python-3.9+-yellowgreen)

把英文论文 PDF 翻成中文 PDF，**版式不动**：在原框位擦掉英文、写中文，双栏、图、表、公式、参考文献的位置一个都不改，读者拿到的仍然是原版纸面。

这是一份 Agent Skill（[SKILL.md](SKILL.md) 是 Agent 的加载入口）加三个可独立运行的脚本：段落靠**行级坐标**抽出，逐页译成 JSON，再由排版引擎写回原框——字号自适应、行距拉伸并底对齐、逐字两端对齐、避头点、项目符号悬挂缩进。

- **不适用**：扫描件（没有文本层，需要先 OCR）；需要重排版式（走 Word / HTML）；目标语言不是中文。
- **版权**：论文原文与其中文译本的版权归原作者与出版方。本仓库只发布流程、代码与规范，不含任何论文 PDF 或译文。

## 目录

```
paper-zh-translation/
├── SKILL.md                    # Agent 入口：触发词、六阶段流程、失败回退
├── README.md / README.en.md    # 本文件
├── requirements.txt
├── scripts/
│   ├── extract_blocks.py       # Phase 1 结构解析（行级块 + 项目符号切分）
│   ├── build_pdf.py            # Phase 3 排版引擎（擦除 + 原位写中文 + 字体子集化）
│   └── qa_check.py             # Phase 4 质检（残留英文 / 越界 / 缺字形 / 丢字）
├── references/
│   ├── translation-json.md     # 译文 JSON 格式与 merge/color/align/skip_first 元数据
│   ├── terminology.md          # 术语对照表 + "首次出现给原词"三条硬规则
│   └── pitfalls.md             # 13 个高频坑：症状 → 原因 → 处理
└── tests/
    └── smoke_test.py           # 合成一篇双栏 PDF，端到端跑 Phase 1 → 3 → 4
```

## 环境

```bash
python -m pip install -r requirements.txt   # PyMuPDF（>=1.24，import pymupdf）+ fonttools
```

中文字体：`build_pdf.py` 首次运行会从 `C:/Windows/Fonts/NotoSerifSC-VF.ttf` 实例化出 400 / 700 两套静态字重再嵌入。这一步不能省——可变字体的默认实例是 ExtraLight(200)，直接读会让整篇字细得不像正文（[pitfalls.md 第 1 条](references/pitfalls.md)）。没有这块字体的机器会回退到系统宋体 + 黑体；字体目录用 `--fonts` 指定。

## 最简跑法

```bash
WORK=翻译工程                       # 所有中间产物放这里，方便改一句话就重建
python scripts/extract_blocks.py paper.pdf "$WORK"
# 读 "$WORK"/seg00.txt，逐页把译文写成 "$WORK"/zh_page00.json（格式见 references/translation-json.md）
python scripts/build_pdf.py --src paper.pdf --work "$WORK"
python scripts/qa_check.py paper_中文翻译.pdf --work "$WORK"
```

常用参数：

| 参数 | 作用 |
|---|---|
| `--pages 3,4` | 只重建指定页（页码从 0 开始），改几页时不必全篇重跑 |
| `--out` | 默认输出 `<原文件名>_中文翻译.pdf`，与源 PDF 同目录 |
| `--fonts` | 实例化字体的存放目录 |
| `--no-justify` | 关掉逐字两端对齐（西文占比高的段落更自然） |
| `--tol` | `qa_check.py` 的横向越界容差，默认 5pt |

## 六个阶段

| 阶段 | 做什么 | 产物 |
|---|---|---|
| 0 环境 | 确认 `pymupdf` / `fontTools` 可导入，准备字体 | `.fonts/`（不入库） |
| 1 解析 | 行级 bbox、字号、粗体；一个块内多条 `• ` 要点切成子块 | `blocks.json`、`segments.json`、`segNN.txt` |
| 2 翻译 | **一次 1~2 页**：读 `segNN.txt`，译文写 `zh_pageNN.json` | 逐页译文 JSON |
| 3 构建 | 擦除原行 → 覆盖撞车的矢量徽标 → 原框位写中文 → 字体子集化 | `<同名>_中文翻译.pdf` |
| 4 质检 | 脚本报数字，人做判断（见下） | 问题清单，非 0 退出码 |
| 5 归档 | PDF 连同 JSON、脚本一起存回 `翻译工程/` | 可复跑的译文工程 |

阶段 2 的两条硬约束：**不合并、不拆分块**（原文断在哪儿，译文就断在哪儿，否则写回时会串栏）；每译 2~3 页就构建一次抽查，别等全书译完才发现某类块漏了。

## 译什么、留什么

| 译成中文 | 保留原文 |
|---|---|
| 标题、摘要、正文、章节标题、图注、表注、致谢、许可声明 | 作者姓名与邮箱、表格单元格、图内文字、伪代码、公式、参考文献条目、`PVLDB Reference Format`、DOI/URL |

数字、百分比、倍数、表号、节号必须与原文一致；术语首次出现给原词（`预训练模型（pre-trained model，PTM）`），之后不再中英摇摆。

## 质检：脚本只报数字，判断靠人

`qa_check.py` 查五项——`english`（残留英文正文）、`over_x`（横向越界）、`over_y`（纵向越界）、`glyph`（缺字形）、`dropped`（中文没落进纸面）。脚本输出 0 不代表可以交付：

- `english` 命中参考文献页、表格页是正常的（已按约定保留英文），命中**正文页**就是漏译，回去补 JSON。
- `glyph` 必须为 0；不为 0 说明译文里有当前字体缺的字符，按 [pitfalls.md 第 3 条](references/pitfalls.md) 换写法。
- 剩下的靠目视：`page.get_pixmap(dpi=120)` 渲染成 PNG，重点看段间空洞、行末标点掉到行首、图注压图、深色底标题是否可见、有没有 `□` 或 `HuggingFace` 这类粘连。
- 至少抽查首页、含图页、多项目符号页、公式页、末页。

## 边界与回退

| 情况 | 处理 |
|---|---|
| 扫描件无文本层 | 明确告知需要 OCR，本流程不适用 |
| 单栏论文 | 流程通用（坐标来自原文，与栏数无关）；只是 `qa_check.py` 的栏边界无意义，忽略越界项 |
| 某页中文溢出 | 压缩该块译文 10~15%，不要靠缩字号硬塞（会与邻段字号不一致） |
| 图注/表注太窄 | 允许缩到 7pt；再不行就精简措辞 |
| 要连表格单元格一起译 | 需要单独重排表格，超出本流程范围 |

## 装成 Agent Skill

```bash
# Claude Code
cp -r paper-zh-translation ~/.claude/skills/
# 或通用 agents skills 目录
cp -r paper-zh-translation ~/.agents/skills/
```

## 自测

```bash
python tests/smoke_test.py
```

合成一篇双栏英文 PDF（1 页 3 段，含项目符号），走完 Phase 1 → 3 → 4，断言页数不变、中文进纸、英文被擦净、`glyph` 与 `dropped` 为 0。实测环境 Python 3.11.9 + PyMuPDF 1.27.2.3，五项问题数均为 0。它只证明流水线在当前环境跑得通，**不能替代真实论文的逐页目视抽查**。

## License

[MIT](LICENSE)，© 2026 Serennity007。代码与本仓库整理的流程文档按 MIT 授权；PyMuPDF 与 AGPL 相关的上游条款、以及任何被你处理的论文本身的版权条款各自适用，翻译与分发论文正文前请确认你有权这样做。
