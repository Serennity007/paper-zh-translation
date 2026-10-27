# paper-zh-translation

**[中文](README.md) | [English](README.en.md)**

![GitHub stars](https://img.shields.io/github/stars/Serennity007/paper-zh-translation?style=flat-square) ![License](https://img.shields.io/github/license/Serennity007/paper-zh-translation?style=flat-square) ![Method](https://img.shields.io/badge/method-in%20place-blue?style=flat-square) ![Language](https://img.shields.io/badge/docs-Chinese%20%7C%20EN-orange?style=flat-square)

An AI skill that turns an English paper PDF into a Chinese one **in place**: paragraphs are extracted by line-level coordinates, translated page by page into JSON, then written back into the original text boxes. Columns, figures, tables, formulas and references keep their positions, so the result still reads like the original page. Ships a six-phase workflow, three standalone scripts, a term table and 13 documented typesetting traps.

- **Copyright**: the papers and any translation of them belong to their authors and publishers. This repository publishes only the workflow, the code and the style rules — no paper PDFs, no translations. Confirm you are entitled to translate and redistribute a paper before you run it through this.
- **Added**: 2026-10-27.

## Install

The repository root *is* the skill directory — copy it into your skills folder:

```bash
# Claude Code
cp -r paper-zh-translation ~/.claude/skills/

# or a shared agents skills directory
cp -r paper-zh-translation ~/.agents/skills/
```

Requirements: `pip install -r requirements.txt` (PyMuPDF ≥ 1.24, fonttools; tested on Python 3.11; no API keys, everything runs locally). The three scripts also work on their own, without an agent.

## When to use it / when not to

- **Use it** for "translate this paper into Chinese", "produce a 中文版 PDF", "make it look like XX_中文翻译.pdf" — where the two-column layout, figure positions and adaptive font size must survive.
- **Don't** if you only want a summary (read the PDF and take notes), if you want a re-typeset document (take the Word / HTML route), for scanned PDFs (no text layer — OCR first), or for any target language other than Chinese.

## Layout

```
paper-zh-translation/
├── SKILL.md                    # skill definition (agent entry: triggers, six phases, fallbacks)
├── README.md / README.en.md
├── requirements.txt
├── scripts/
│   ├── extract_blocks.py       # Phase 1 structure parsing (line boxes + bullet splitting)
│   ├── build_pdf.py            # Phase 3 engine (erase + rewrite in place + font subsetting)
│   └── qa_check.py             # Phase 4 QA (leftover English / overflow / missing glyphs)
├── references/
│   ├── translation-json.md     # translation JSON format, merge / color / align / skip_first
│   ├── terminology.md          # term tables (data reduction / model training / DB) + caption style
│   └── pitfalls.md             # 13 recurring traps: symptom -> cause -> fix
└── tests/
    └── smoke_test.py           # synthesises a two-column PDF and runs Phase 1 -> 3 -> 4
```

`SKILL.md` and `references/*.md` are written in Chinese: the rules they encode are about Chinese typesetting (line-start punctuation, term pairing, hanging indents) and the vocabulary of the papers being translated.

## Environment

```bash
python -m pip install -r requirements.txt
python -c "import pymupdf, fontTools; print('ok')"
```

Fonts: on first run `build_pdf.py` instantiates static 400 and 700 weights from `C:/Windows/Fonts/NotoSerifSC-VF.ttf` before embedding them. This cannot be skipped — the default instance of that variable font is ExtraLight (200), which makes the whole document look impossibly thin ([pitfalls.md #1](references/pitfalls.md)). Machines without it fall back to the system serif + hei fonts; relocate with `--fonts`.

## Quick start

```bash
WORK=translation-work           # keep every intermediate here so a one-line fix stays cheap
python scripts/extract_blocks.py paper.pdf "$WORK"
# read "$WORK"/seg00.txt, translate page by page into "$WORK"/zh_page00.json
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
| 0 Setup | check `pymupdf` / `fontTools`, prepare fonts | instantiated fonts (never committed) |
| 1 Parse | line bboxes, sizes, bold; a block holding several `• ` bullets is split into sub-blocks | `blocks.json`, `segments.json`, `segNN.txt` |
| 2 Translate | **1–2 pages at a time**: read `segNN.txt`, write `zh_pageNN.json` | per-page translation JSON |
| 3 Build | erase each original line, white out colliding vector badges, write Chinese into the original box, subset fonts | `<name>_中文翻译.pdf` |
| 4 QA | the script reports numbers, the human decides (below) | issue list, non-zero exit on problems |
| 5 Archive | keep the PDF together with the JSONs and scripts | a rerunnable translation project |

## What gets translated, what stays

| Into Chinese | Left as-is |
|---|---|
| Title, abstract, body, section headings, figure and table captions, acknowledgements, licence notice | Author names and emails, table cells, text drawn inside figures, pseudocode, formulas, reference entries, `PVLDB Reference Format`, DOIs and URLs |

## Four hard rules

1. **No re-typesetting.** Only "replace the text and re-break the lines inside that block" — column widths, line rhythm and figure coordinates stay untouched.
2. **Never merge or split blocks.** The source breaks where it breaks; sentences chopped by an inline formula are rejoined with `merge` and the fragments get `""`, otherwise the rewrite spills into the neighbouring column.
3. **Numbers and reference marks are frozen.** Figures, percentages, speedups, table and section numbers must match the source; no unfounded polish. Terms get their source language on first use — `预训练模型 (pre-trained model, PTM)` — then stay consistent.
4. **QA is not optional.** Rebuild and spot-check every 2–3 pages, rather than discovering a whole missed block class after the last page.

## QA: the script reports, the human decides

`qa_check.py` checks five things — `english` (leftover body English), `over_x`, `over_y`, `glyph` (missing glyphs) and `dropped` (Chinese that never reached the page). A clean run is not yet a deliverable:

- `english` hits on reference and table pages are expected; a hit on a **body page** is a missed translation — go back to the JSON.
- `glyph` must be 0; anything else means your translation uses a character the current CJK font lacks ([pitfalls.md #3](references/pitfalls.md)).
- The rest is visual: render with `page.get_pixmap(dpi=120)` and look for gaps between paragraphs, punctuation that fell to the start of a line, captions sitting on figures, white-on-dark headings, and `□` boxes or glued words like `HuggingFace`.
- At minimum check page 1, a figure page, a bullet-heavy page, a formula page and the last page.

## Limits and fallbacks

| Situation | What to do |
|---|---|
| Scanned PDF, no text layer | say so: OCR is required, this workflow does not apply |
| Single-column paper | the workflow is the same (coordinates come from the source); only the column-boundary checks in `qa_check.py` are meaningless — ignore the overflow items |
| Chinese overflows on one page | compress that block's translation by 10–15%; do not force it with a smaller size, which would mismatch the neighbouring paragraph |
| Caption box too narrow | shrinking to 7pt is allowed; past that, cut wording |
| "Translate the table cells too" | needs separate table re-layout, out of scope here |

## Provenance and measurements

- The workflow, term tables and pitfall list come from actually translating two-column papers in PVLDB format into Chinese; the numbers quoted in the docs are real run records (e.g. [pitfalls.md #2](references/pitfalls.md): a 14-page translation going from 22 MB+ to 1.9 MB). **No source PDFs and no translations are shipped**; historical numbers do not substitute for measuring your own paper.
- **Self-test on this repo, 2026-10-27**: `python tests/smoke_test.py` builds a synthetic one-page two-column English PDF (3 blocks, with bullets) and runs Phase 1 → 3 → 4 — all five counters at 0, page count unchanged, Chinese landed, English erased. Environment Python 3.11.9 + PyMuPDF 1.27.2.3. It proves the pipeline runs in your environment; **it does not replace reading the real pages**.

## Roadmap

The two-column PDF route gets stabilised first. Translating table cells, an OCR front-end for scans and non-Chinese targets are not planned. `references/terminology.md` covers three term groups (data reduction / model training / databases); for another field, add a table in the same format instead of letting the body text mix languages.

## License

[MIT](LICENSE), © 2026 Serennity007. The code and the workflow notes in this repository are MIT; PyMuPDF carries its own (AGPL / commercial) terms, and so does any paper you run through this pipeline.
