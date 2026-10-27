# -*- coding: utf-8 -*-
"""端到端自检：合成一篇双栏英文 PDF，跑完 Phase 1 → 3 → 4。

用法：
    python tests/smoke_test.py

不依赖任何真实论文，用来确认三个脚本在当前环境里能串起来跑通，
并且中文确实写进了输出 PDF。翻译内容是无意义的占位句，只验排版链路。
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")

BODY = (
    "Data reduction techniques have been studied for many years in the storage "
    "community because they lower the footprint of large archives. Deduplication "
    "finds identical chunks and keeps a single copy, while delta compression removes "
    "the redundancy that remains inside similar objects. We measure both throughput "
    "and compression ratio on a sampled workload and report the difference. "
)
ZH = (
    "数据缩减技术长期受到存储社区的关注，因为它直接降低大规模归档的存储占用。"
    "去重找出完全相同的数据块并只保留一份副本，增量压缩则消除相似对象内部剩余的冗余。"
    "我们在采样数据集上同时测量吞吐量与压缩率，并报告两者之间的差异。"
)


def make_pdf(path):
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)  # A4
    for rect in (pymupdf.Rect(50, 60, 285, 700), pymupdf.Rect(310, 60, 545, 700)):
        page.insert_textbox(rect, BODY * 3, fontsize=9, fontname="helv", lineheight=1.25)
    page.insert_textbox(
        pymupdf.Rect(50, 720, 545, 780),
        "* Scale. We sampled nine hundred models and recorded their layer counts.\n"
        "* Storage. The compressed size dropped below every baseline we tried.",
        fontsize=9, fontname="helv", lineheight=1.25,
    )
    doc.save(path)
    doc.close()


def run(script, *args):
    proc = subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    print("--- %s (exit %d)" % (script, proc.returncode))
    for line in (proc.stdout or "").splitlines():
        print("   ", line)
    if proc.returncode != 0:
        for line in (proc.stderr or "").splitlines():
            print("  ERR", line)
        raise SystemExit("%s failed" % script)
    return proc.stdout


def main():
    work = tempfile.mkdtemp(prefix="paper-zh-smoke-")
    try:
        src = os.path.join(work, "demo.pdf")
        out = os.path.join(work, "demo_zh.pdf")
        make_pdf(src)

        run("extract_blocks.py", src, work)
        segs = json.load(open(os.path.join(work, "segments.json"), encoding="utf-8"))
        print("segments:", len(segs))
        if not segs:
            raise SystemExit("Phase 1 produced no segments")

        by_page = {}
        for seg in segs:
            by_page.setdefault(seg["p"], {})[seg["id"]] = ZH
        for pno, mapping in sorted(by_page.items()):
            json.dump(mapping, open(os.path.join(work, "zh_page%02d.json" % pno), "w",
                                    encoding="utf-8"), ensure_ascii=False)

        run("build_pdf.py", "--src", src, "--work", work, "--out", out,
            "--fonts", os.path.join(work, ".fonts"))
        qa = run("qa_check.py", out, "--work", work, "--src", src)

        import pymupdf
        src_doc, out_doc = pymupdf.open(src), pymupdf.open(out)
        assert out_doc.page_count == src_doc.page_count, "page count changed"
        text = "".join(out_doc[i].get_text() for i in range(out_doc.page_count))
        assert "数据缩减" in text, "Chinese text not found in output"
        assert "Data reduction techniques" not in text, "English body not erased"

        glyph = int(re.search(r"\[glyph\] (\d+)", qa).group(1))
        dropped = int(re.search(r"\[dropped\] (\d+)", qa).group(1))
        print("checks: glyph=%d dropped=%d pagecount=%d" % (glyph, dropped, out_doc.page_count))
        if glyph or dropped:
            raise SystemExit("glyph/dropped problems, see report above")
        print("SMOKE OK")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
