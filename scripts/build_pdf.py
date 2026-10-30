# -*- coding: utf-8 -*-
"""Phase 3：把译文写回原 PDF，保持双栏版式、图表位置、公式与参考文献不动。

用法：
    python build_pdf.py --src <paper.pdf> --work <workdir> [--out <out.pdf>]
                        [--pages 0,1,2] [--fonts C:/Windows/Fonts]

workdir 中需要：
    segments.json     由 extract_blocks.py 生成
    zh_pageNN.json    逐页译文（见 references/translation-json.md）

排版规则（都是踩过坑换来的，改动前先读 references/pitfalls.md）：
    1. 擦除原英文行 → 在原块 bbox 内重写中文，绝不重排分栏/图表。
    2. 字号自适应：原字号放得下就用原字号，放不下才 0.1pt 递减（下限 6.2pt）。
    3. 行距自适应 + 底对齐：中文更短时拉伸行距（上限 1.60×）填满原槽位，
       末行基线对齐原块末行，避免段间出现大空洞。
    4. 逐字两端对齐：把行尾余量均摊到字符间隙（不拉伸西文单词内部）。
    5. 避头点：行末标点先挤 1~2 个汉字下移，实在挤不下才允许悬挂溢出。
    6. 项目符号悬挂缩进：• 顶格，其续行缩进 1.05 字宽。
    7. 原文正文里的小圆形徽标（Stage 2a / 1a）与中文必然撞车 → 白底覆盖。
    8. 数学字母（U+1D400 段）在 CJK 字体里没有字形 → NFKC 归一为 ASCII。
"""
import argparse
import os
import sys
import unicodedata

import pymupdf
from translation_io import load_segments, load_zh, validate_page_count

NO_LINE_START = '，。、；：？！）》」』】”’%…·'

FONT = None
BOLD = None
SERIF = None
BOLD_PATH = None


# ---------------------------------------------------------------- 字体
def ensure_fonts(font_dir):
    """准备正文字体与粗体：优先从 Noto Serif SC 可变字体实例化 400/700。"""
    global SERIF, BOLD_PATH
    os.makedirs(font_dir, exist_ok=True)
    regular = os.path.join(font_dir, 'zh-regular.ttf')
    bold = os.path.join(font_dir, 'zh-bold.ttf')
    if os.path.exists(regular) and os.path.exists(bold):
        SERIF, BOLD_PATH = regular, bold
        return

    vf = 'C:/Windows/Fonts/NotoSerifSC-VF.ttf'
    if os.path.exists(vf):
        from fontTools.ttLib import TTFont
        from fontTools.varLib.instancer import instantiateVariableFont
        for weight, path in ((400, regular), (700, bold)):
            f = TTFont(vf)
            # 关键：可变字体默认实例可能是 ExtraLight(200)，直接读会得到极细字重
            instantiateVariableFont(f, {"wght": weight}, inplace=True, updateFontNames=True)
            f.save(path)
        SERIF, BOLD_PATH = regular, bold
        return

    # 退路：系统宋体 + 黑体
    for cand in ('C:/Windows/Fonts/simsun.ttc', 'C:/Windows/Fonts/STSONG.TTF',
                 'C:/Windows/Fonts/simfang.ttf'):
        if os.path.exists(cand):
            SERIF = cand
            break
    else:
        sys.exit('未找到可用的中文字体，请用 --fonts 指定')
    BOLD_PATH = ('C:/Windows/Fonts/simhei.ttf'
                 if os.path.exists('C:/Windows/Fonts/simhei.ttf') else SERIF)


# ---------------------------------------------------------------- 文本清洗
def sanitize(text):
    """数学字母等 CJK 字体缺失的字符转成 ASCII 等价形式。"""
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


def tokenize(text):
    """-> [(token, bold)]；汉字逐字成 token（可断行），西文单词整体，空格单独。"""
    toks = []
    i, n, bold = 0, len(text), False
    while i < n:
        if text.startswith('**', i):
            bold = not bold
            i += 2
            continue
        ch = text[i]
        if ch == '\n':
            toks.append(('\n', bold)); i += 1
        elif ch == ' ':
            j = i
            while j < n and text[j] == ' ':
                j += 1
            toks.append((' ', bold)); i = j
        elif ord(ch) < 0x2e80:
            j = i
            while j < n and ord(text[j]) < 0x2e80 and text[j] not in ' \n' \
                    and not text.startswith('**', j):
                j += 1
            toks.append((text[i:j], bold)); i = j
        else:
            toks.append((ch, bold)); i += 1
    return toks


def wof(tok, size):
    return (BOLD if tok[1] else FONT).text_length(tok[0], fontsize=size)


# ---------------------------------------------------------------- 断行
def layout(tokens, size, width, first_indent=0.0, hang=0.0):
    """贪心断行 -> [[x偏移, token 列表]]；支持首行缩进与项目符号悬挂缩进。"""
    space = FONT.text_length(' ', fontsize=size)
    lines = []
    cur, cur_w, pend = [], 0.0, False
    cur_off, grp_hang = first_indent, 0.0
    lim = width - cur_off
    for tok in tokens:
        if tok[0] == '\n':
            lines.append([cur_off, cur])
            cur, cur_w, pend = [], 0.0, False
            cur_off, grp_hang = 0.0, 0.0
            lim = width
            continue
        if tok[0] == ' ':
            pend = True
            continue
        if not cur and tok[0].startswith('•') and hang:
            grp_hang = hang
            lim = width - cur_off
        w = wof(tok, size)
        add = w + (space if (pend and cur) else 0)
        if pend and cur:
            cur.append((' ', tok[1]))
        if cur and cur_w + add > lim:
            if tok[0][0] in NO_LINE_START:
                # 标点不许落行首：把它连同行尾 1~2 个字符一起移到下一行；
                # 整行都被搬空时退化为悬挂（标点留在本行末尾，允许轻微溢出）。
                carry = []
                while cur and len(carry) < 2 and cur_w + w > lim:
                    last = cur.pop()
                    carry.insert(0, last)
                    cur_w -= wof(last, size)
                if cur:
                    lines.append([cur_off, cur])
                    cur = carry + [tok]
                    cur_w = sum(wof(c, size) for c in cur)
                    cur_off = grp_hang
                    lim = width - cur_off
                else:
                    cur = carry + [tok]          # 悬挂，不丢 token
                    cur_w = sum(wof(c, size) for c in cur)
            else:
                lines.append([cur_off, cur])
                cur, cur_w = [tok], w
                cur_off = grp_hang
                lim = width - cur_off
        else:
            cur.append(tok)
            cur_w += add
        pend = False
    if cur:
        lines.append([cur_off, cur])
    return lines


def draw(page, x, y, line, size, extra=0.0, color=(0, 0, 0)):
    segs = []
    for t, b in line:
        if extra:                      # 两端对齐：逐 token 保留，才能均摊间隙
            segs.append((t, b))
        elif segs and segs[-1][1] == b:
            segs[-1] = (segs[-1][0] + t, b)
        else:
            segs.append((t, b))
    for k, (t, b) in enumerate(segs):
        if t:
            page.insert_text((x, y), t, fontsize=size,
                             fontname='FB' if b else 'F', color=color)
            x += (BOLD if b else FONT).text_length(t, fontsize=size)
        if extra and k < len(segs) - 1:
            x += extra


def place(page, bb, text, orig_size, bold_all=False, align='left',
          last_baseline=None, indent=0.0, justify=True, color=(0, 0, 0), top=False):
    tokens = tokenize(sanitize(text))
    if bold_all:
        tokens = [(t, True) for t, _ in tokens]
    if bb.width < 130:                 # 并排窄图注留一点右侧余量
        bb = pymupdf.Rect(bb.x0, bb.y0, bb.x1 - 4, bb.y1)
    # 单栏宽的块不许越过栏间空白（合并/公式框常比栏宽多出几个 pt）
    mid = page.rect.width / 2
    if bb.x0 < mid - 30 and bb.x1 < mid + 40:        # 左栏块（可能略越界）
        bb = pymupdf.Rect(bb.x0, bb.y0, min(bb.x1, mid - 18), bb.y1)
    elif bb.x0 > mid - 40 and bb.x1 > mid + 30:      # 右栏块（可能略左溢）
        bb = pymupdf.Rect(max(bb.x0, mid + 18), bb.y0, bb.x1, bb.y1)

    bullet = text.lstrip().startswith('•')

    def room_for(sz):
        """首行之外、可分摊 (n-1) 个行距的竖向空间。"""
        if top:
            return bb.height - sz * 0.95
        bl = last_baseline if last_baseline is not None else bb.y0 + sz * 1.02
        return (bl - bb.y0) - sz * 0.95

    min_lead = 1.08                                  # 行距下限（比默认 1.20 更紧）
    size = orig_size
    while size > 6.2:
        lines = layout(tokens, size, bb.width, indent, size * 1.05 if bullet else 0.0)
        n_try = len(lines)
        if n_try <= 1 or (n_try - 1) * min_lead * size <= room_for(size) + 0.6:
            break
        size -= 0.1
    if size < orig_size - 0.6:
        print(f'  [warn] 字号 {orig_size:.1f} -> {size:.1f}pt | {text[:18]}')
    lines = layout(tokens, size, bb.width, indent, size * 1.05 if bullet else 0.0)
    n = len(lines)

    base_last = last_baseline if last_baseline is not None else bb.y0 + size * 1.02
    if n > 1:
        # 行距 = 余量/(n-1)，夹在 [1.08×, 上限] 之间（1~2 行短段上限 1.35×）
        slack = room_for(size)
        cap = size * (1.35 if n <= 2 else 1.60)
        lead = max(size * min_lead, min(slack / (n - 1), cap))
    else:
        lead = size * 1.20
    y = (bb.y0 + size * 0.95) if top else (base_last - (n - 1) * lead)
    if y < bb.y0 + size * 0.95:
        y = bb.y0 + size * 0.95

    for i, (off, line) in enumerate(lines):
        lw = sum(wof(t, size) for t in line)
        x = bb.x0 + off
        extra = 0.0
        if align == 'center':
            x = bb.x0 + max(0.0, (bb.width - lw) / 2)
        elif justify and i < n - 1:
            gap = bb.width - off - lw - 0.6
            if len(line) > 1 and 0 < gap < size * 2.6:
                extra = gap / (len(line) - 1)
        draw(page, x, y, line, size, extra, color)
        y += lead


# ---------------------------------------------------------------- 主流程
def main():
    global FONT, BOLD
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True)
    ap.add_argument('--work', required=True)
    ap.add_argument('--out')
    ap.add_argument('--pages', help='只重建部分页，如 0,1,2（页码从 0 开始）')
    ap.add_argument('--fonts', default=os.path.expanduser('~/.workbuddy/cache/paper-zh-fonts'))
    ap.add_argument('--no-justify', action='store_true')
    args = ap.parse_args()

    out = args.out or os.path.join(
        os.path.dirname(os.path.abspath(args.src)),
        os.path.splitext(os.path.basename(args.src))[0] + '_中文翻译.pdf')
    try:
        segs = load_segments(args.work)
        zh, meta = load_zh(args.work, segs)
        pages = {int(x) for x in args.pages.split(',')} if args.pages is not None else None
        doc = pymupdf.open(args.src)
        validate_page_count(segs, doc.page_count)
        if pages is not None and (not pages or min(pages) < 0 or max(pages) >= doc.page_count):
            raise ValueError('--pages must contain existing 0-based page numbers.')
        if pages is not None and not any(s['p'] in pages and s['id'] in zh for s in segs):
            raise ValueError('No translation entries on the pages selected by --pages.')
    except (OSError, ValueError) as error:
        ap.error(str(error))

    ensure_fonts(os.path.abspath(args.fonts))
    FONT = pymupdf.Font(fontfile=SERIF)
    BOLD = pymupdf.Font(fontfile=BOLD_PATH)
    for pno in range(doc.page_count):
        if pages and pno not in pages:
            continue
        page = doc[pno]
        todo = [s for s in segs if s['p'] == pno and s['id'] in zh]
        if not todo:
            continue

        segbox = {s['id']: pymupdf.Rect(s['bbox']) for s in segs if s['p'] == pno}
        _w = sorted((b.x1 - b.x0) for b in segbox.values())
        col_w = _w[int(len(_w) * 0.9)] if _w else page.rect.width
        jobs, covered = [], set()
        for s in todo:
            info = meta.get(s['id'], {})
            bb = pymupdf.Rect(s['bbox'])
            if info.get('merge'):      # 被公式/分数切碎的多个块合成一个框
                cand = pymupdf.Rect(s['bbox'])
                for mid in info['merge']:
                    if mid in segbox:
                        cand |= segbox[mid]
                if cand.width > col_w * 1.12:
                    # 跨栏的块不能合并（合并后框会横跨两栏，正文会盖到邻栏）
                    print(f'  [warn] 忽略跨栏 merge: {s["id"]}')
                else:
                    bb = cand
                    covered.update(info['merge'])
            if s['id'] in covered or not zh[s['id']].strip():
                continue               # 只擦不写
            jobs.append((s, bb, info))

        # 1) 精确到行地擦除原文（skip_first 保留行首徽标/编号，不擦）
        jobids = {s['id'] for s, _, _ in jobs}
        for s in todo:
            skip = meta.get(s['id'], {}).get('skip_first', 0)
            for i, ln in enumerate(s['lines']):
                r = pymupdf.Rect(ln['bbox'])
                r.x0 -= 0.6; r.x1 += 0.8; r.y0 -= 0.45; r.y1 += 0.55
                if i == 0 and skip and s['id'] in jobids:
                    r.x0 = ln['bbox'][0] + skip - 0.6
                page.add_redact_annot(r)
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE,
                              graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
                              text=pymupdf.PDF_REDACT_TEXT_REMOVE)
        page.insert_font(fontname='F', fontfile=SERIF)
        page.insert_font(fontname='FB', fontfile=BOLD_PATH)

        # 2) 覆盖正文里的小黑圆徽标（Stage 2a / 1a …），译文已用文字表达
        badges = [d for d in page.get_drawings()
                  if d.get('fill') is not None and sum(d['fill']) < 0.2
                  and 3 < d['rect'].width < 16 and 3 < d['rect'].height < 16
                  and d['rect'].get_area() > 8]
        for _, bb, _ in jobs:
            for d in badges:
                if d['rect'].intersects(bb):
                    page.draw_rect(d['rect'] + (-0.6, -0.6, 0.6, 0.6),
                                   color=None, fill=(1, 1, 1))

        # 3) 原位写中文
        for s, bb, info in jobs:
            last = None
            if info.get('merge'):
                last = bb.y1 - 1.8          # 合并块：以合并后框底为末行基线
            elif len(s['lines']) > 1:
                last = s['lines'][-1]['bbox'][3] - s['lines'][-1]['sz'] * 0.20
            ind = 0.0
            if len(s['lines']) > 1 and not zh[s['id']].startswith(('•', '∗', '*')):
                ind = s['lines'][0]['bbox'][0] - min(l['bbox'][0] for l in s['lines'])
                ind = ind if 3 < ind < 20 else 0.0
            place(page, bb, zh[s['id']], info.get('sz', s['lines'][0]['sz']),
                  bold_all=info.get('bold', s['bold']),
                  align=info.get('align', 'left'),
                  last_baseline=last,
                  indent=info.get('indent', info.get('skip_first', ind)),
                  justify=not args.no_justify,
                  color=info.get('color', (0, 0, 0)),
                  top=info.get('top', False))

    doc.set_metadata({
        'title': os.path.splitext(os.path.basename(out))[0],
        'subject': '中文译文（原位替换式排版，保留原文版式与图表位置）',
        'creator': 'paper-zh-translation skill',
        'producer': 'PyMuPDF',
    })
    doc.subset_fonts(verbose=False)    # 关键：不做子集化，每页都会重复嵌入整套字库
    doc.save(out, garbage=4, deflate=True, clean=True)
    print('saved', out)


if __name__ == '__main__':
    main()
