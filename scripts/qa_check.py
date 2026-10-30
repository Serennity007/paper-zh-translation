# -*- coding: utf-8 -*-
"""Phase 4：译文 PDF 质检（每次 build 之后都必须跑）。

用法：
    python qa_check.py <out.pdf> --work <workdir> [--src <paper.pdf>]

检查项：
    1. 残留英文正文：译完仍是大段英文的块（参考文献、表格、图内文字属正常，需人工判断）
    2. 横向越界：行右端超出本栏右边界 2pt 以上
    3. 纵向越界：行落到页面底部页脚区
    4. 缺字形：译文里含有当前中文字体没有的字符（会渲染成方框）

退出码非 0 表示有需要修的问题。
"""
import argparse
import os
import re
import sys

import pymupdf
from translation_io import load_segments, load_zh, validate_page_count

CJK = re.compile(r'[\u4e00-\u9fff]')
LAT = re.compile(r'[A-Za-z]')

# 这些内容按约定保留英文，不算"漏译"
KEEP_HINTS = ('PVLDB Reference Format', 'REFERENCES', 'doi:', 'https://',
              'Proceedings of the VLDB', 'This work is licensed')


def sanitize(text):
    import unicodedata
    out = []
    for ch in text:
        o = ord(ch)
        if 0x1D400 <= o <= 0x1D7FF or 0x2100 <= o <= 0x214F:
            ch = unicodedata.normalize('NFKC', ch)
        elif ch == '\u27e8':
            ch = '\u3008'
        elif ch == '\u27e9':
            ch = '\u3009'
        out.append(ch)
    return ''.join(out).replace('\u20d7', '').replace('\u20d2', '')


def column_edges(src):
    """从原文里统计左右栏的右边界（正文行会填满栏宽）。"""
    doc = pymupdf.open(src)
    left, right = [], []
    for page in doc:
        w = page.rect.width
        for b in page.get_text('dict')['blocks']:
            if b['type'] != 0:
                continue
            for l in b['lines']:
                sz = max((s['size'] for s in l['spans']), default=0)
                if not (6 <= sz <= 12):
                    continue
                x0, x1 = l['bbox'][0], l['bbox'][2]
                if x1 < w / 2 + 5:
                    left.append(x1)
                elif x0 > w / 2 - 5:
                    right.append(x1)
    # 取 99.5 分位而不是最大值：避免个别悬挂标点把边界抬高
    f = lambda a, d: (sorted(a)[min(len(a) - 1, int(len(a) * 0.995))] if a else d)
    return f(left, 296), f(right, 559)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf')
    ap.add_argument('--work', required=True)
    ap.add_argument('--src')
    ap.add_argument('--fonts',
                    default=os.path.expanduser('~/.workbuddy/cache/paper-zh-fonts'))
    ap.add_argument('--tol', type=float, default=5.0,
                    help='横向越界容差（pt）；悬挂标点与字形advance误差通常<=4pt')
    args = ap.parse_args()

    try:
        segments = load_segments(args.work)
        zh, meta = load_zh(args.work, segments)
        doc = pymupdf.open(args.pdf)
        validate_page_count(segments, doc.page_count)
    except (OSError, ValueError) as error:
        ap.error(str(error))

    src = args.src
    if not src:
        cand = args.pdf.replace('_中文翻译', '')
        src = cand if os.path.exists(cand) else None
    l_right, r_right = column_edges(src) if src else (296, 559)

    problems = {'english': [], 'over_x': [], 'over_y': [], 'glyph': [], 'dropped': []}

    # 1) 残留英文
    for pno in range(doc.page_count):
        for b in doc[pno].get_text('dict')['blocks']:
            if b['type'] != 0:
                continue
            t = ' '.join(''.join(s['text'] for s in l['spans']) for l in b['lines']).strip()
            if not t or any(h in t for h in KEEP_HINTS):
                continue
            zh_chars, en_chars = len(CJK.findall(t)), len(LAT.findall(t))
            digits = sum(c.isdigit() for c in t)
            # 表格行（数字多）、参考文献条目（[12] 年份）按约定保留英文，不算漏译
            if digits / max(len(t), 1) > 0.12 or re.search(r'\[\d+\]', t):
                continue
            if re.search(r'\b(19|20)\d{2}\b\s*\.', t):   # 参考文献条目（含年份）
                continue
            if en_chars > 60 and zh_chars < 20:
                problems['english'].append((pno, t[:70]))

    # 2/3) 越界
    for pno in range(doc.page_count):
        page = doc[pno]
        for b in page.get_text('dict')['blocks']:
            if b['type'] != 0:
                continue
            for l in b['lines']:
                t = ''.join(s['text'] for s in l['spans']).strip()
                if not t:
                    continue
                x0, _, x1, y1 = l['bbox']
                if t.isdigit():          # 页脚页码
                    continue
                mid = page.rect.width / 2
                if x1 <= mid + 2:        # 左栏
                    edge = l_right
                elif x0 >= mid - 2:      # 右栏
                    edge = r_right
                else:                    # 跨栏（标题/整宽图注/作者块），不判越界
                    continue
                if x1 > edge + args.tol and CJK.search(t):
                    problems['over_x'].append((pno, round(x1, 1), t[:36]))
                if y1 > page.rect.height - 25:
                    problems['over_y'].append((pno, round(y1, 1), t[:36]))

    # 4) 缺字形（用构建时缓存的静态字体检查）
    font = None
    reg = os.path.join(os.path.abspath(args.fonts), 'zh-regular.ttf')
    if os.path.exists(reg):
        font = pymupdf.Font(fontfile=reg)
    elif os.path.exists('C:/Windows/Fonts/simsun.ttc'):
        font = pymupdf.Font(fontfile='C:/Windows/Fonts/simsun.ttc')
    if font:
        bad = set()
        for text in zh.values():
            for ch in sanitize(text):
                if ch not in '\n\r\t' and not font.has_glyph(ord(ch)):
                    bad.add(ch)
        problems['glyph'] = sorted(bad)

    # 5) 丢字：按段落框从输出 PDF 里回抽文本，与译文比汉字数
    segfile = os.path.join(args.work, 'segments.json')
    if os.path.exists(segfile):
        segs = {s['id']: s for s in segments}
        for sid, text in zh.items():
            if not text.strip() or sid not in segs:
                continue
            seg = segs[sid]
            box = pymupdf.Rect(seg['bbox'])
            for mid in meta.get(sid, {}).get('merge', []):
                if mid in segs:
                    box |= pymupdf.Rect(segs[mid]['bbox'])
            pno = seg['p']
            if pno >= doc.page_count:
                continue
            got = doc[pno].get_text('text', clip=box + (-2, -2, 3, 3))
            # 子集字体的 ToUnicode 可能把部分汉字映射成兼容表意字（U+F900–FAFF），
            # 先 NFKC 归一，避免把"字形正常"误判成"丢字"
            import unicodedata as _ud
            want = len(CJK.findall(_ud.normalize('NFKC', text)))
            have = len(CJK.findall(_ud.normalize('NFKC', got)))
            if want >= 8 and have < want * 0.92:
                problems['dropped'].append((pno, sid, f'{have}/{want}', text[:26]))

    total = 0
    for name, items in problems.items():
        n = len(items)
        total += n
        print(f'[{name}] {n}')
        for it in items[:12]:
            print('   ', it)
    print('pages', doc.page_count, 'issues', total)
    sys.exit(0 if total == 0 else 1)


if __name__ == '__main__':
    main()
