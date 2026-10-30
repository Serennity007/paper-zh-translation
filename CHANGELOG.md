# Maintenance changes

## 2026-10-30

- Build and QA now validate translation IDs against `segments.json` and page filenames. Previously, unknown IDs were silently ignored and duplicate keys could overwrite translations; a short untranslated PDF could even pass QA with an unknown ID.
- Reject duplicate JSON keys within/across files, non-text translations, malformed metadata and merge targets that are missing, on another page or not explicitly empty. UTF-8 BOM input is accepted.
- Reject invalid `--pages`, pages outside the PDF and selected pages without translation entries before preparing fonts or saving the output. Partial translations and documented empty merge fragments remain supported.
- Add 14 regression tests and retain the synthetic end-to-end smoke test. The smoke test now uses the build's actual font directory for QA and UTF-8 subprocess output.

本次修复译文被静默忽略或覆盖，以及错误输入仍可能质检通过的问题。验证使用合成 PDF 和占位译文，不涉及真实论文，也不构成真实论文排版或翻译质量验证。
