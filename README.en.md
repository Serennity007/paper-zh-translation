# paper-zh-translation

**[中文](README.md) | [English](README.en.md)**

![License](https://img.shields.io/badge/License-MIT-blue)
![Engine](https://img.shields.io/badge/engine-PyMuPDF-lightgrey)
![Python](https://img.shields.io/badge/python-3.9+-yellowgreen)

Translate an English paper PDF into Chinese **without touching the layout**: the English line is erased inside its own box and the Chinese is written back into that same box. Columns, figures, tables, formulas and references stay where they were, so the result still reads like the original page.

It ships as an Agent Skill ([SKILL.md](SKILL.md) is the agent entry point) plus three scripts you can run on their own. Paragraphs are extracted from **line-level coordinates**, translated page by page into JSON, then re-typeset by a layout engine: adaptive font size, stretched leading that is bottom-aligned, per-character justification, line-start punctuation rules and hanging indents for bullets.

- **Not for**: scanned PDFs (no text layer — they need OCR first), re-typeset output (use a Word / HTML route), or target languages other than Chinese.
- **Copyright**: the original papers and any Chinese translation of them belong to their authors and publishers. This repository publishes only the workflow, the code and the style rules — no paper PDFs, no translations.

## Layout

```
paper-zh-translation/
├── SKILL.md                    # agent entry: triggers, six phases, fallbacks
├── README.md / README.en.md
├── requirements.txt
├── scripts/
│   ├── extract_blocks.py       # Phase 1 structure parsing (line boxes + bullet splitting)
│   ├── build_pdf.py            # Phase 3 engine (erase + rewrite in place + font subsetting)
│   └── qa_check.py             # Phase 4 QA (leftover English / overflow / missing glyphs)
├── references/
│   ├── translation-json.md     # translation JSON format, merge/color/align/skip_first metadata
│   ├── terminology.md          # term table + the "give the source term on first use" rules
│   └── pitfalls.md             # 13 recurring traps: symptom -> cause -> fix
└── tests/
    └── smoke_test.py           # synthesises a two-column PDF and runs Phase 1 -> 3 -> 4
```

Note: `references/*.md` and `SKILL.md` are written in Chinese, because the rules they encode are about Chinese typesetting (line-start punctuation, term pairing, bullet hanging indent).

## Requirements

```bash
python -m pip install -r requirements.txt   # PyMuPDF (>=1.24, `import pymupdf`) + fonttools
```

Fonts: on first run `build_pdf.py` instantiates static 400 and 700 weights from `C:/Windows/Fonts/NotoSerifSC-VF.ttf` before embedding them. This step cannot be skipped — the default instance of that variable font is ExtraLight (200), and using it directly makes the whole document look impossibly thin ([pitfalls.md #1](references/pitfalls.md)). Machines without that font fall back to the system serif + hei fonts; point `--fonts` anywhere you like.

## Quick start

```bash
WORK=translation-work           # keep every intermediate here so a one-line fix stays cheap
python scripts/extract_blocks.py paper.pdf "$WORK"
# read "$WORK"/seg00.txt, translate page by page into "$WORK"/zh_page00.json
# (format: references/translation-json.md)
python scripts/build_pdf.py --src paper.pdf --work "$WORK"
python scripts/qa_check.py paper_中文翻译.pdf --work "$WORK"
```

Flags you will actually use:

| Flag | Effect |
|---|---|
| `--pages 3,4` | rebuild only those pages (0-based) instead of the whole document |
| `--out` | default output is `<source-name>_中文翻译.pdf`, next to the source |
| `--fonts` | where the instantiated fonts live |
| `--no-justify` | turn off per-character justification (reads better in Latin-heavy paragraphs) |
| `--tol` | horizontal overflow tolerance for `qa_check.py`, default 5pt |

## The six phases

| Phase | What happens | Output |
|---|---|---|
| 0 Setup | check `pymupdf` / `fontTools` import, prepare fonts | `.fonts/` (never committed) |
| 1 Parse | line bboxes, sizes, bold; a block holding several `• ` bullets is split into sub-blocks | `blocks.json`, `segments.json`, `segNN.txt` |
| 2 Translate | **1–2 pages at a time**: read `segNN.txt`, write `zh_pageNN.json` | per-page translation JSON |
| 3 Build | erase each original line, white out colliding vector badges, write Chinese into the original box, subset fonts | `<name>_中文翻译.pdf` |
| 4 QA | the script reports numbers, the human makes the calls (below) | issue list, non-zero exit on problems |
| 5 Archive | keep the PDF together with the JSONs and scripts | a rerunnable translation project |

Two hard rules in phase 2: **never merge or split blocks** (the source breaks where it breaks, or the rewrite spills into the neighbouring column), and rebuild every 2–3 pages so a whole class of missed blocks surfaces early.

## What gets translated, what stays

| Into Chinese | Left as-is |
|---|---|
| Title, abstract, body, section headings, figure and table captions, acknowledgements, licence notice | Author names and emails, table cells, text drawn inside figures, pseudocode, formulas, reference entries, `PVLDB Reference Format`, DOIs and URLs |

Numbers, percentages, speedups, table and section references must match the source exactly. Terms get their source language on first use — `预训练模型 (pre-trained model, PTM)` — and are then used consistently.

## QA: the script reports, the human decides

`qa_check.py` checks five things — `english` (leftover body English), `over_x`, `over_y`, `glyph` (missing glyphs) and `dropped` (Chinese that never reached the page). A clean script run is not yet a deliverable:

- `english` hits on reference and table pages are expected (that text is kept by design); a hit on a **body page** is a missed translation.
- `glyph` must be 0; anything else means your translation uses a character the current CJK font lacks — see [pitfalls.md #3](references/pitfalls.md).
- Everything else is visual: render pages with `page.get_pixmap(dpi=120)` and look for gaps between paragraphs, punctuation that fell to the start of a line, captions sitting on figures, white-on-dark headings, and `□` boxes or glued words like `HuggingFace`.
- At minimum check page 1, a figure page, a bullet-heavy page, a formula page and the last page.

## Limits and fallbacks

| Situation | What to do |
|---|---|
| Scanned PDF, no text layer | say so: OCR is required, this workflow does not apply |
| Single-column paper | the workflow is the same (coordinates come from the source); only the column-boundary checks in `qa_check.py` are meaningless — ignore the overflow items |
| Chinese overflows on one page | compress that block's translation by 10–15%; do not force it with a smaller size, which would mismatch the neighbouring paragraph |
| Caption box too narrow | shrinking to 7pt is allowed; past that, cut wording |
| "Translate the table cells too" | needs separate table re-layout, out of scope here |

## Install as an Agent Skill

```bash
# Claude Code
cp -r paper-zh-translation ~/.claude/skills/
# or a shared agents skills directory
cp -r paper-zh-translation ~/.agents/skills/
```

## Self-test

```bash
python tests/smoke_test.py
```

It builds a synthetic one-page two-column English PDF (3 blocks, with bullets), runs Phase 1 → 3 → 4, and asserts the page count is unchanged, the Chinese landed, the English is gone, and `glyph` and `dropped` are both 0. Verified here on Python 3.11.9 + PyMuPDF 1.27.2.3 with all five counters at 0. It proves the pipeline runs in your environment — **it does not replace reading the real pages**.

## License

[MIT](LICENSE), © 2026 Serennity007. The code and the workflow notes in this repository are MIT; PyMuPDF carries its own (AGPL/commercial) terms, and so does any paper you run through this pipeline — make sure you are entitled to translate and distribute it before you do.
