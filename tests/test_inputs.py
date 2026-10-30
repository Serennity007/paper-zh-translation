"""Reject translation mistakes before fonts, redactions or output writes."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import build_pdf


class TranslationInputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.segments = [
            {'id': 'p0b0', 'p': 0, 'bbox': [50, 50, 200, 100], 'lines': [], 'bold': False},
            {'id': 'p0b1', 'p': 0, 'bbox': [50, 100, 200, 150], 'lines': [], 'bold': False},
            {'id': 'p1b0', 'p': 1, 'bbox': [50, 50, 200, 100], 'lines': [], 'bold': False},
        ]
        self.write('segments.json', self.segments)

    def write(self, name, data):
        (self.work / name).write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')

    def load(self):
        return build_pdf.load_zh(str(self.work))

    def test_valid_partial_translation_and_merge(self):
        self.write('zh_page00.json', {'p0b0': '完整译文', 'p0b1': '', '@p0b0': {'merge': ['p0b1'], 'top': True}})
        zh, meta = self.load()
        self.assertEqual(zh, {'p0b0': '完整译文', 'p0b1': ''})
        self.assertEqual(meta['p0b0']['merge'], ['p0b1'])

    def test_missing_or_empty_translations_are_rejected(self):
        with self.assertRaises(ValueError):
            self.load()
        self.write('zh_page00.json', {})
        with self.assertRaises(ValueError):
            self.load()

    def test_unknown_segment_is_not_silently_ignored(self):
        self.write('zh_page00.json', {'p0b9999': '应该被检查的译文'})
        with self.assertRaisesRegex(ValueError, 'p0b9999'):
            self.load()

    def test_wrong_page_file_is_rejected(self):
        self.write('zh_page01.json', {'p0b0': '放错页的译文'})
        with self.assertRaises(ValueError):
            self.load()

    def test_utf8_bom_is_accepted(self):
        (self.work / 'zh_page00.json').write_text('{"p0b0":"中文译文"}', encoding='utf-8-sig')
        self.assertEqual(self.load()[0]['p0b0'], '中文译文')

    def test_duplicate_keys_in_one_json_are_rejected(self):
        (self.work / 'zh_page00.json').write_text('{"p0b0":"first","p0b0":"second"}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'p0b0'):
            self.load()

    def test_duplicate_keys_across_files_are_rejected(self):
        self.write('zh_page0.json', {'p0b0': 'first'})
        self.write('zh_page00.json', {'p0b0': 'second'})
        with self.assertRaisesRegex(ValueError, 'p0b0'):
            self.load()

    def test_non_text_and_non_object_inputs_are_rejected(self):
        for data in ([1], {'p0b0': 123}, {'p0b0': 'text', '@p0b0': 'not metadata'}):
            with self.subTest(data=data):
                self.write('zh_page00.json', data)
                with self.assertRaises(ValueError):
                    self.load()

    def test_invalid_merge_targets_are_rejected(self):
        for target in ('p0b999', 'p1b0', 'p0b0'):
            self.write('zh_page00.json', {'p0b0': 'main', '@p0b0': {'merge': [target]}})
            with self.subTest(target=target), self.assertRaises(ValueError):
                self.load()

    def test_merge_target_must_be_explicitly_empty(self):
        for fragment in (None, 'would be rendered twice'):
            data = {'p0b0': 'main', '@p0b0': {'merge': ['p0b1']}}
            if fragment is not None:
                data['p0b1'] = fragment
            self.write('zh_page00.json', data)
            with self.subTest(fragment=fragment), self.assertRaises(ValueError):
                self.load()

    def test_invalid_input_preserves_output_before_font_setup(self):
        self.write('zh_page00.json', {'p0b9999': 'typo'})
        out = self.work / 'existing.pdf'
        out.write_bytes(b'previous PDF must survive')
        args = ['build_pdf.py', '--src', str(self.work / 'missing.pdf'), '--work', str(self.work), '--out', str(out)]
        with patch.object(sys, 'argv', args), patch.object(build_pdf, 'ensure_fonts') as fonts, contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            build_pdf.main()
        self.assertEqual(error.exception.code, 2)
        fonts.assert_not_called()
        self.assertEqual(out.read_bytes(), b'previous PDF must survive')

    def test_invalid_page_selection_is_rejected_before_fonts(self):
        import pymupdf
        src = self.work / 'source.pdf'
        with pymupdf.open() as doc:
            doc.new_page()
            doc.new_page()
            doc.save(src)
        self.write('zh_page00.json', {'p0b0': '译文'})
        for pages in ('-1', '2', '', 'wrong', '1'):
            args = ['build_pdf.py', '--src', str(src), '--work', str(self.work), '--pages', pages]
            with self.subTest(pages=pages), patch.object(sys, 'argv', args), patch.object(build_pdf, 'ensure_fonts') as fonts, contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                build_pdf.main()
            self.assertEqual(error.exception.code, 2)
            fonts.assert_not_called()

    def test_segments_outside_pdf_are_rejected(self):
        from translation_io import validate_page_count
        with self.assertRaisesRegex(ValueError, 'p1b0'):
            validate_page_count(self.segments, 1)

    def test_qa_rejects_unknown_id_instead_of_reporting_zero_issues(self):
        import pymupdf
        pdf = self.work / 'short.pdf'
        with pymupdf.open() as doc:
            page = doc.new_page()
            page.insert_text((50, 70), 'A brief example.')
            doc.save(pdf)
        self.write('zh_page00.json', {'p0b9999': '这段译文完全没有写进论文。'})
        result = subprocess.run([sys.executable, '-X', 'utf8', str(SCRIPTS / 'qa_check.py'), str(pdf), '--work', str(self.work)], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('p0b9999', result.stderr.decode('utf-8'))


if __name__ == '__main__':
    unittest.main()
