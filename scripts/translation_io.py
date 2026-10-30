"""Read one translation project without silently losing duplicate/unknown IDs."""
import json
from pathlib import Path
import re


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def _read(path):
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'), object_pairs_hook=_unique_object)
    except (OSError, ValueError) as error:
        raise ValueError(f'{path.name}: {error}') from error


def load_segments(work):
    segments = _read(Path(work) / 'segments.json')
    if not isinstance(segments, list):
        raise ValueError('segments.json must be a list; rerun extract_blocks.py.')
    seen = set()
    for segment in segments:
        if (not isinstance(segment, dict) or not isinstance(segment.get('id'), str)
                or not segment['id'] or type(segment.get('p')) is not int or segment['p'] < 0):
            raise ValueError('segments.json contains an invalid segment ID or page.')
        if segment['id'] in seen:
            raise ValueError(f'Duplicate segment ID: {segment["id"]}')
        seen.add(segment['id'])
    return segments


def load_zh(work, segments=None):
    segments = load_segments(work) if segments is None else segments
    by_id = {s['id']: s for s in segments}
    zh, meta, seen = {}, {}, set()
    for path in sorted(Path(work).glob('zh_page*.json')):
        match = re.fullmatch(r'zh_page(\d+)\.json', path.name)
        if not match:
            raise ValueError(f'{path.name}: expected zh_pageNN.json.')
        page = int(match[1])
        data = _read(path)
        if not isinstance(data, dict):
            raise ValueError(f'{path.name}: translations must be a JSON object.')
        for key, value in data.items():
            if key in seen:
                raise ValueError(f'{path.name}: duplicate translation key {key}.')
            seen.add(key)
            sid = key[1:] if key.startswith('@') else key
            if sid not in by_id:
                raise ValueError(f'{path.name}: unknown segment ID {sid}; check segments.json.')
            if by_id[sid]['p'] != page:
                raise ValueError(f'{path.name}: {sid} belongs to page {by_id[sid]["p"]:02d}.')
            if key.startswith('@'):
                if not isinstance(value, dict):
                    raise ValueError(f'{path.name}: metadata for {sid} must be an object.')
                meta[sid] = value
            else:
                if not isinstance(value, str):
                    raise ValueError(f'{path.name}: translation for {sid} must be text.')
                zh[sid] = value
    if not zh:
        raise ValueError('No translations found; create zh_pageNN.json before build or QA.')
    for sid, info in meta.items():
        if sid not in zh:
            raise ValueError(f'{sid}: metadata requires a translation entry.')
        targets = info.get('merge', [])
        if not isinstance(targets, list) or any(not isinstance(t, str) for t in targets):
            raise ValueError(f'{sid}: merge must be a list of segment IDs.')
        for target in targets:
            if target == sid or target not in by_id or by_id[target]['p'] != by_id[sid]['p']:
                raise ValueError(f'{sid}: invalid merge target {target}; use another segment on the same page.')
            if zh.get(target) != '':
                raise ValueError(f'{sid}: merge target {target} must have an explicit empty translation.')
    return zh, meta


def validate_page_count(segments, page_count):
    for segment in segments:
        if segment['p'] >= page_count:
            raise ValueError(f'{segment["id"]}: page {segment["p"]} is outside this PDF; check the source/work directory.')
