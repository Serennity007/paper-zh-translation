# paper-zh-translation

**[中文](README.md) | [English](README.en.md)**

[项目总导航](https://github.com/Serennity007/repo-catalog/blob/main/README.zh-CN.md) · [维护记录](CHANGELOG.md)

![GitHub stars](https://img.shields.io/github/stars/Serennity007/paper-zh-translation?style=flat-square) ![License](https://img.shields.io/github/license/Serennity007/paper-zh-translation?style=flat-square) ![译法](https://img.shields.io/badge/译法-原位替换-blue?style=flat-square) ![语言](https://img.shields.io/badge/语言-中文%20%7C%20EN-orange?style=flat-square)

学术论文 PDF 中文翻译 AI Skill：把英文论文**原位**换成中文——段落按行级坐标抽出，逐页译成 JSON，再由排版引擎写回原来的文本框。分栏、图、表、公式、参考文献的位置一个都不动，读者拿到的仍然是原版纸面。附六阶段流程、三个可独立运行的脚本、术语规范与 13 条排版坑清单。

- **版权与免责**：论文原文及其译文的版权归作者与出版方所有。本仓库只发布流程、代码与规范，不含任何论文 PDF 或译文；翻译并分发论文正文前，请确认你有权这样做。
- **收录日期**：2026-10-27。

## 使用说明

整个仓库就是一个技能目录，复制到你自己的技能目录即可：

```bash
# Claude Code
cp -r paper-zh-translation ~/.claude/skills/

# 或通用 agents skills 目录
cp -r paper-zh-translation ~/.agents/skills/
```

依赖：`pip install -r requirements.txt`（PyMuPDF ≥ 1.24、fonttools，Python 3.11 实测；无需任何 API key，全程本地）。三个脚本也能脱离 Agent 单独跑。

## 什么时候用 / 不要用

- **用**：「把这篇论文翻译成中文」「生成中文版 PDF」「照着 XX_中文翻译.pdf 的样子翻这篇」，且要求双栏版式、图片位置、字号自适应都不变。
- **不用**：只要摘要与要点（直接读 PDF 写笔记更划算）；需要重排版式（走 Word / HTML）；扫描件（无文本层，得先 OCR）；目标语言不是中文。

## 目录

```
paper-zh-translation/
├── SKILL.md                    # 技能定义（Agent 加载入口：触发词、六阶段、失败回退）
├── README.md / README.en.md    # 双语说明
├── requirements.txt
├── scripts/
│   ├── extract_blocks.py       # Phase 1 结构解析（行级块 + 项目符号切分）
│   ├── build_pdf.py            # Phase 3 排版引擎（擦除 + 原位写中文 + 字体子集化）
│   ├── qa_check.py             # Phase 4 质检（残留英文 / 越界 / 缺字形 / 丢字）
│   └── translation_io.py       # 构建与质检共享的译文输入校验
├── references/
│   ├── translation-json.md     # 译文 JSON 格式、merge / color / align / skip_first 元数据
│   ├── terminology.md          # 数据缩减 / 模型训练 / 数据库三组术语对照 + 图注写法
│   └── pitfalls.md             # 13 个高频坑：症状 → 原因 → 处理
└── tests/
    ├── smoke_test.py           # 合成一篇双栏 PDF，端到端跑 Phase 1 → 3 → 4
    └── test_inputs.py          # 错误段落 ID、重复键、页码、merge 与输出保护回归
```

## 环境

```bash
python -m pip install -r requirements.txt
python -c "import pymupdf, fontTools; print('ok')"
```

中文字体：`build_pdf.py` 首次运行自动从 `C:/Windows/Fonts/NotoSerifSC-VF.ttf` 实例化 400 / 700 两套静态字重再嵌入。这一步不能省——可变字体默认实例是 ExtraLight(200)，直接读会让整篇字细得不像正文（[pitfalls.md 第 1 条](references/pitfalls.md)）。没有这块字体的机器回退系统宋体 + 黑体，字体目录用 `--fonts` 指定。

## 最简跑法

```bash
WORK=翻译工程                       # 中间产物都放这里，改一句话就能重建
python scripts/extract_blocks.py paper.pdf "$WORK"
# 读 "$WORK"/seg00.txt，逐页把译文写成 "$WORK"/zh_page00.json（格式见 references/translation-json.md）
python scripts/build_pdf.py --src paper.pdf --work "$WORK"
python scripts/qa_check.py paper_中文翻译.pdf --work "$WORK" --src paper.pdf
```

常用参数：

| 参数 | 作用 |
|---|---|
| `--pages 3,4` | 只重建指定页（页码从 0 开始），改几页时不必全篇重跑 |
| `--out` | 默认输出 `<原文件名>_中文翻译.pdf`，与源 PDF 同目录 |
| `--fonts` | 实例化字体的存放目录 |
| `--no-justify` | 关掉逐字两端对齐（西文占比高的段落更自然） |
| `--tol` | `qa_check.py` 的横向越界容差，默认 5pt |

构建和质检会先核对 `segments.json` 与译文：不存在的段落 ID、放错页的条目、重复 JSON 键、非文本译文及无效 `merge` 均返回非零退出码，错误会标出文件名或段落 ID。构建失败发生在字体准备和写 PDF 之前；已有输出不会被这些输入错误覆盖。只翻译一部分段落仍然支持，未列入 JSON 的块保留原文；`merge` 的碎片目标必须显式写成 `""`。

三个入口脚本依赖同目录的 `translation_io.py`，单独使用时请保留整个 `scripts/` 目录。若构建时传了自定义 `--fonts`，质检也需传同一个目录。

```bash
python -m unittest discover -s tests -p test_inputs.py -v
python tests/smoke_test.py
```

## 六个阶段

| 阶段 | 做什么 | 产物 |
|---|---|---|
| 0 环境 | 确认 `pymupdf` / `fontTools` 可导入，准备字体 | 实例化字体（不入库） |
| 1 解析 | 行级 bbox、字号、粗体；一个块内多条 `• ` 要点切成子块 | `blocks.json`、`segments.json`、`segNN.txt` |
| 2 翻译 | **一次 1~2 页**：读 `segNN.txt`，译文写 `zh_pageNN.json` | 逐页译文 JSON |
| 3 构建 | 擦除原行 → 覆盖撞车的矢量徽标 → 原框位写中文 → 字体子集化 | `<同名>_中文翻译.pdf` |
| 4 质检 | 脚本报数字、人做判断（见下） | 问题清单，有问题退出码非 0 |
| 5 归档 | PDF 连同 JSON、脚本一起存回 `翻译工程/` | 可复跑的译文工程 |

## 译什么、留什么

| 译成中文 | 保留原文 |
|---|---|
| 标题、摘要、正文、章节标题、图注、表注、致谢、许可声明 | 作者姓名与邮箱、表格单元格、图内文字、伪代码、公式、参考文献条目、`PVLDB Reference Format`、DOI/URL |

## 四条红线

1. **不重排**。只做「文本替换 + 段内重排行」，不改栏宽、行数节奏、图表坐标。
2. **不合并、不拆分块**。原文断在哪儿，译文就断在哪儿；被公式切碎的句子用 `merge` 并框，碎片块写 `""`，否则写回时会串到邻栏。
3. **数字与编号不许动**。数字、百分比、倍数、表号、节号必须与原文一致，不做无根据的润色；术语首次出现给原词（`预训练模型（pre-trained model，PTM）`），之后不再中英摇摆。
4. **质检不许跳**。每译 2~3 页就构建一次抽查，别等全书译完才发现某类块漏了。

## 质检：脚本只报数字，判断靠人

`qa_check.py` 查五项——`english`（残留英文正文）、`over_x`（横向越界）、`over_y`（纵向越界）、`glyph`（缺字形）、`dropped`（中文没落进纸面）。跑成 0 也不代表能交付：

- `english` 命中参考文献页、表格页是正常的（按约定保留英文），命中**正文页**就是漏译，回去补 JSON。
- `glyph` 必须为 0；不为 0 说明译文里有当前字体缺的字符，按 [pitfalls.md 第 3 条](references/pitfalls.md) 换写法。
- 其余靠目视：`page.get_pixmap(dpi=120)` 渲染成 PNG，重点看段间空洞、行末标点掉到行首、图注压图、深色底标题是否可见、有没有 `□` 或 `HuggingFace` 这类中英粘连。
- 至少抽查首页（标题/作者/摘要）、含图页、多项目符号页、公式页、末页。

## 边界与回退

| 情况 | 处理 |
|---|---|
| 扫描件无文本层 | 明确告知需要 OCR，本流程不适用 |
| 单栏论文 | 流程通用（坐标来自原文，与栏数无关）；只是 `qa_check.py` 的栏边界无意义，忽略越界项 |
| 某页中文溢出 | 压缩该块译文 10~15%，不要靠缩字号硬塞（会与邻段字号不一致） |
| 图注 / 表注太窄 | 允许缩到 7pt；再不行就精简措辞（「……如下所示」这类可删） |
| 要连表格单元格一起译 | 需要单独重排表格，超出本流程范围，说明风险后按需处理 |

## 来源与实测

- 流程、术语表与坑清单沉淀自把双栏论文（PVLDB 版式）译成中文的实战，文档里的数字来自当时的实测记录（如 [pitfalls.md 第 2 条](references/pitfalls.md)：14 页译文从 22 MB+ 降到 1.9 MB）。**原始论文 PDF 与译文未随仓库提供**，历史实测数字不能代替你自己那篇论文的实测。
- **2026-10-27 本仓库自检**：`python tests/smoke_test.py`（合成 1 页双栏英文 PDF，3 段含项目符号，走完 Phase 1 → 3 → 4）→ `english / over_x / over_y / glyph / dropped` 全部为 0，页数不变、中文进纸、英文擦净。环境 Python 3.11.9 + PyMuPDF 1.27.2.3。它只证明流水线在当前环境跑得通，**不能替代真实论文的逐页目视抽查**。

## 路线图

先把双栏 PDF 这一条路跑稳。表格单元格翻译、扫描件 OCR 前置、非中文目标语言暂不在计划内；`references/terminology.md` 只覆盖数据缩减 / 模型训练 / 数据库三组术语，换领域请按同一格式补一张表，别在正文里中英混用。

## License

[MIT](LICENSE)，© 2026 Serennity007。代码与本仓库整理的流程文档按 MIT 授权；PyMuPDF 的 AGPL / 商用条款、以及任何被你处理的论文本身的版权条款各自适用。
