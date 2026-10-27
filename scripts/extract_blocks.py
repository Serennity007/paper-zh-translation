# -*- coding: utf-8 -*-
"""Phase 1：把论文 PDF 拆成可翻译的段落单元。

用法：
    python extract_blocks.py <src.pdf> <workdir>

产出（写入 workdir）：
    blocks.json     原始文本块（行级 bbox / 字号 / 粗体），按页
    segments.json   实际排版单元：含多个 "• " 项目符号的块会被切成子块，
                    每个单元带 id / 页码 / bbox / 是否整体加粗
    segNN.txt       供人工阅读、逐页翻译的纯文本清单（含 id 与行数）

设计要点：
- 用行级 bbox 而不是块级，后面擦除原文可以精确到行，不会误删图注/表格线。
- 项目符号块必须切分：一个块里常有 3~5 条并列要点，整块当一段翻译会丢结构。
- 首个项目符号之前的正文（_pre）必须单独保留，否则会被吞掉。
- 是否加粗按"字符数加权"判定：标题行常是粗体、正文行不是，逐行判定会误判整段。
"""
import json
import os
import re
import sys
import collections

import pymupdf


def classify(line):
    spans = line['spans']
    text = "".join(s['text'] for s in spans)
    size = max((round(s['size'], 1) for s in spans), default=0.0)
    bold = any(('TB' in s['font']) or ('Bold' in s['font']) or ('Black' in s['font'])
               for s in spans)
    ital = any(s['font'].endswith('TI') or ('Italic' in s['font']) for s in spans)
    return {
        't': text,
        'bbox': [round(v, 2) for v in line['bbox']],
        'sz': size,
        'bold': bold,
        'ital': ital,
    }


def extract(src):
    doc = pymupdf.open(src)
    blocks = []
    for pno, page in enumerate(doc):
        for bidx, b in enumerate(page.get_text('dict')['blocks']):
            if b['type'] != 0:
                continue
            lines = [classify(l) for l in b['lines']]
            lines = [l for l in lines if l['t'].strip()]
            if not lines:
                continue
            # 字符数加权判断整块是否加粗（>60% 字符为粗体才算）
            nb = sum(len(l['t']) for l in lines if l['bold'])
            na = sum(len(l['t']) for l in lines)
            blocks.append({
                'p': pno,
                'b': bidx,
                'id': f'p{pno}b{bidx}',
                'bbox': [round(v, 2) for v in b['bbox']],
                'bold': nb > na * 0.6,
                'lines': lines,
            })
    return blocks


def split_segments(blocks):
    """把含多个 bullet 的块切成子块；保留首个 bullet 之前的正文（_pre）。"""
    segs = []
    for bl in blocks:
        lines = bl['lines']
        starts = [i for i, l in enumerate(lines) if l['t'].lstrip().startswith('•')]
        if len(starts) <= 1:
            segs.append({'id': bl['id'], 'p': bl['p'], 'lines': lines, 'bold': bl['bold']})
            continue
        if starts[0] > 0:
            segs.append({'id': f"{bl['id']}_pre", 'p': bl['p'],
                         'lines': lines[:starts[0]], 'bold': bl['bold']})
        bounds = starts + [len(lines)]
        for k in range(len(starts)):
            segs.append({'id': f"{bl['id']}_{k}", 'p': bl['p'],
                         'lines': lines[bounds[k]:bounds[k + 1]], 'bold': bl['bold']})
    for s in segs:
        x0 = min(l['bbox'][0] for l in s['lines'])
        x1 = max(l['bbox'][2] for l in s['lines'])
        y0 = s['lines'][0]['bbox'][1]
        y1 = s['lines'][-1]['bbox'][3]
        s['bbox'] = [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)]
    return segs


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    src, work = sys.argv[1], sys.argv[2]
    os.makedirs(work, exist_ok=True)
    blocks = extract(src)
    segs = split_segments(blocks)
    json.dump(blocks, open(os.path.join(work, 'blocks.json'), 'w', encoding='utf-8'),
              ensure_ascii=False)
    json.dump(segs, open(os.path.join(work, 'segments.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=0)

    bypage = collections.defaultdict(list)
    for s in segs:
        bypage[s['p']].append(s)
    for pno in sorted(bypage):
        chunks = []
        for s in bypage[pno]:
            txt = "\n".join(l['t'] for l in s['lines'])
            chunks.append(f"[{s['id']}] sz={s['lines'][0]['sz']} "
                          f"b={int(s['lines'][0]['bold'])} n={len(s['lines'])}\n{txt}")
        open(os.path.join(work, f'seg{pno:02d}.txt'), 'w', encoding='utf-8').write(
            "\n\n".join(chunks))
    print(f'blocks={len(blocks)} segments={len(segs)} pages={len(bypage)} -> {work}')


if __name__ == '__main__':
    main()
