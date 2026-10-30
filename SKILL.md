---
name: paper-zh-translation
description: Translates English academic PDFs (CS / database / machine-learning papers) into Chinese while keeping the original page layout — same two columns, same figure and table positions, formulas and citation numbers untouched. Paragraphs are extracted with line-level coordinates, translated page by page into JSON, then redrawn into the original text boxes with adaptive font size, justified Chinese typography and bottom-anchored leading. This skill should be used when the user asks to translate a paper PDF into Chinese, produce a 中文翻译 / 中文版 PDF, or asks for a Chinese version that must not disturb the original layout.
agent_created: true
---

# 学术论文 PDF 中文翻译（原位替换式）

把一篇英文论文 PDF 变成中文 PDF：**擦掉英文正文，在原框位写中文**——分栏、图、表、公式、参考文献的位置一个都不动，读者拿到的仍然是原版纸面。

## 什么时候用

- "把这篇论文翻译成中文" / "生成中文版 PDF" / "照着 XX_中文翻译.pdf 的样子翻这篇"
- 要求"保持原版双栏排版、图片位置不变、字号自适应"
- 用户给的是 PDF（扫描版不行，需要可选文本层）

**不要用**：只需要摘要/要点（直接读 PDF 写笔记更划算）、需要重排版式（应走 Word/HTML 路线）、目标语言不是中文。

## 核心原则

1. **不重排**。只做"文本替换 + 段内重排行"，不改栏宽、行数节奏、图表坐标。
2. **译什么 / 留什么** 固定：

   | 译成中文 | 保留原文 |
   |---|---|
   | 标题、摘要、正文、章节标题、图注、表注、致谢、许可声明 | 作者姓名与邮箱、表格单元格、图内文字、伪代码、公式、参考文献条目、`PVLDB Reference Format`、DOI/URL |

3. **术语一次定死**，首次出现给原词，之后不再中英摇摆（见 `references/terminology.md`）。
4. **不做无根据的润色**：数字、百分比、倍数、表号、节号必须与原文一致；原文的粗体、斜体强调位置尽量保留。

## 工作流

先建工作目录（建议 `<论文目录>/翻译工程/`），所有中间产物都放里面，最后随 PDF 一起归档，方便下次改一句话就重建。

### Phase 0 · 环境与字体

```bash
python -c "import pymupdf, fontTools; print('ok')"
```

`build_pdf.py` 首次运行会自动从 `C:/Windows/Fonts/NotoSerifSC-VF.ttf` 实例化 400/700 两套静态字体存到 `.fonts/`（可变字体默认字重是 ExtraLight，直接读会让整篇字极细——见 `references/pitfalls.md` 第 1 条）。非 Windows 或没有该字体时，用 `--fonts` 指向别处，脚本会回退到系统宋体 + 黑体。

### Phase 1 · 结构解析

```bash
python scripts/extract_blocks.py <paper.pdf> <workdir>
```

产出：`blocks.json`（行级坐标/字号/粗体）、`segments.json`（排版单元）、`segNN.txt`（逐页待译文本）。

要点：
- 含多条 `• ` 的块会被切成子块（`_0/_1/…`），首个要点之前的正文单独成 `_pre` 块。
- 检查 `segNN.txt`：图内文字、公式、表格单元格也会出现在里面，这些**不译**——不放进 JSON 就不会被动。

### Phase 2 · 逐页翻译

**一次处理 1~2 页**：读 `segNN.txt`，把译文写进 `zh_pageNN.json`（格式见 `references/translation-json.md`）。

- 先通读整页再动笔，保证指代一致（"these models" 要落到具体名词）。
- 逐块译，**不合并、不拆分块**（Phase 1 已切好的除外）；原文断在哪儿，译文就断在哪儿。
- 项目符号要点用 `"• **规模。**我们从……"`，一条要点一个段落（块内多条用 `\n• ` 分隔）。
- 图注写 `"**图 3：**不同类别的模型层数累积分布（CDF）。"`
- "一句话被公式切成两块"时用 `merge` 并成一个框，碎片块写 `""`（见 json 格式说明）。
- 嵌在正文里的黑圆徽标（Stage 2a 之类）当普通文字写进译文（"在阶段 2a……"），构建时会自动盖掉徽标。
- **每译完 2~3 页就构建一次抽查**，别等全书译完才发现某类块漏了。

### Phase 3 · 构建

```bash
python scripts/build_pdf.py --src <paper.pdf> --work <workdir>
# 只重建某几页（页码从 0 开始）
python scripts/build_pdf.py --src <paper.pdf> --work <workdir> --pages 3,4
```

构建前会核对段落 ID、逐页 JSON、重复键和 `merge`，输入错误返回退出码 2 并保留已有输出。先修正报告中的文件或 ID 再重跑，不要忽略错误。三个入口脚本需要同目录的 `translation_io.py`，归档或复制时保留整个 `scripts/` 目录。

引擎做的事（改脚本前先读 `references/pitfalls.md`）：行级擦除 → 覆盖撞车徽标 → 原框位写中文（字号自适应下探到 6.2pt、行距 1.20~1.60× 自适应并底对齐、逐字两端对齐、避头点、项目符号悬挂缩进）→ 字体子集化 → 写元数据 → 输出 `<同名>_中文翻译.pdf`。

### Phase 4 · 质检（必做，不许跳）

```bash
python scripts/qa_check.py <out.pdf> --work <workdir> --src <paper.pdf>
```

质检也会先验证输入；自定义字体目录时传入与构建相同的 `--fonts`。脚本查五类：残留英文正文、横向越界（默认容差 5pt，悬挂标点与字形 advance 误差通常 ≤4pt）、纵向越界、缺字形、译文丢字。**脚本只报数字，判断靠人**：

- `english` 命中参考文献页、表格页是正常的（脚本已过滤数字密集行、`[12]` 引用行、含年份的条目）；命中**正文页**就是漏译，回去补 JSON。
- `glyph` 必须为 0；不为 0 说明译文里有当前字体缺字形的字符，按 `references/pitfalls.md` 第 3 条换字符。
- 逐页目视抽查（`page.get_pixmap(dpi=120)` 渲染成 PNG 看），重点看：① 段间有没有大空洞 ② 行末标点有没有掉到行首 ③ 图注/表注有没有压到图上 ④ 深色底标题是否可见 ⑤ 有没有 `□` 或中英粘连（`HuggingFace`）。
- 至少检查：首页（标题/作者/摘要）、含图页、多项目符号页、公式页、末页（结论/致谢/参考文献起始）。

### Phase 5 · 交付与归档

- 用 `present_files` 交付 PDF；回复里说明**译了什么、留了什么**，以及本次特有的处理（例如某图注特别长做了并框）。
- 把 `blocks.json`、`segments.json`、`zh_page*.json`、两个脚本、`说明.md` 一起归档到 `<论文目录>/翻译工程/`；`.fonts/` 不进归档（会自动重建）。
- 清理临时 PNG / 预览 PDF。

## 失败与回退

| 情况 | 处理 |
|---|---|
| PDF 无文本层（扫描件） | 明确告知需要 OCR，本流程不适用 |
| 单栏论文 | 流程通用（坐标来自原文，与栏数无关）；只是 `qa_check.py` 的栏边界无意义，忽略越界项 |
| 某页重排后中文明显溢出 | 压缩该块译文 10~15%，不要靠缩字号硬塞（会与邻段字号不一致） |
| 图注/表注空间太窄放不下 | 允许缩到 7pt；再不行就精简措辞（"……如下所示"这类可删） |
| 用户要求"顺带把表格也译了" | 需要单独重排表格，超出本流程范围；说明风险后按需处理 |

## 资源

- `scripts/extract_blocks.py` —— Phase 1 结构解析（行级块 + 项目符号切分）
- `scripts/build_pdf.py` —— Phase 3 排版引擎（擦除 + 原位写中文 + 字体子集化）
- `scripts/qa_check.py` —— Phase 4 质检（残留英文 / 越界 / 缺字形）
- `references/translation-json.md` —— 译文 JSON 格式、`merge`/`color`/`align` 元数据、数学符号写法
- `references/terminology.md` —— 数据缩减/模型训练/数据库三组术语对照 + 图注写法
- `references/pitfalls.md` —— 13 个高频坑：症状、原因、处理
