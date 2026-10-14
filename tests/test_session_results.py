import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook
from streamlit.testing.v1 import AppTest

import comparison
import converter
from session_results import CACHE_KEY

ROOT = Path(__file__).resolve().parents[1]
CSV = b'name,sku,price,stock\nCup,000101,12.95,10\n'


def uploader_for(files):
    def upload(*args, **kwargs):
        side = {'upload_old': 'old', 'upload_new': 'new'}.get(kwargs.get('key'))
        if side is None or files[side] is None:
            return None
        filename, data = files[side]
        file = BytesIO(data)
        file.name = filename
        return file
    return upload


def app():
    return AppTest.from_file(str(ROOT / 'streamlit_app.py')).run(timeout=60)


class SessionResultTests(unittest.TestCase):
    def test_language_and_supplier_controls_reuse_processing_but_translate_report(self):
        with patch('converter.read_supplier_file', wraps=converter.read_supplier_file) as read, \
             patch('converter.convert_products', wraps=converter.convert_products) as validate, \
             patch('comparison.compare_products', wraps=comparison.compare_products) as compare:
            view = app()
            baseline = (read.call_count, validate.call_count, compare.call_count)
            self.assertEqual(baseline, (2, 2, 1))
            view.selectbox(key='language').set_value('Nederlands').run(timeout=60)
            self.assertEqual(view.dataframe[-1].value['Wijziging'].iloc[0], 'Prijs gewijzigd')
            view.text_input[0].set_value('Saved supplier').run(timeout=60)
            view.button(key='save_profile_old').click().run(timeout=60)
            view.selectbox(key='supplier_old').set_value('Saved supplier').run(timeout=60)
            self.assertEqual(len(view.exception), 0)
            self.assertEqual((read.call_count, validate.call_count, compare.call_count), baseline)
            self.assertEqual([m.value for m in view.metric], ['100', '100', '5'])

    def test_same_filename_changed_content_invalid_file_and_removal_never_show_stale_report(self):
        files = {'old': ('same.csv', CSV), 'new': ('same.csv', CSV.replace(b'12.95', b'14.95'))}
        with patch('streamlit.file_uploader', side_effect=uploader_for(files)), \
             patch('converter.read_supplier_file', wraps=converter.read_supplier_file) as read, \
             patch('converter.convert_products', wraps=converter.convert_products) as validate, \
             patch('comparison.compare_products', wraps=comparison.compare_products) as compare:
            view = app()
            read.reset_mock(); validate.reset_mock(); compare.reset_mock()
            view.radio(key='source_mode').set_value('upload').run(timeout=60)
            self.assertEqual((read.call_count, validate.call_count, compare.call_count), (2, 2, 1))
            for price in (b'19.95', b'21.95'):
                files['new'] = ('same.csv', CSV.replace(b'12.95', price))
                view.run(timeout=60)
                self.assertEqual(view.dataframe[-1].value['New value'].iloc[0], price.decode())
                self.assertEqual(len(view.session_state[CACHE_KEY]), 5)
            self.assertEqual((read.call_count, validate.call_count, compare.call_count), (4, 4, 3))
            files['new'] = ('same.csv', CSV.replace(b'12.95', b'bad'))
            view.run(timeout=60)
            self.assertEqual(len(view.metric), 0)
            self.assertNotIn('comparison', view.session_state[CACHE_KEY])
            self.assertEqual(compare.call_count, 3)
            baseline = (read.call_count, validate.call_count)
            view.selectbox(key='language').set_value('Nederlands').run(timeout=60)
            self.assertEqual((read.call_count, validate.call_count), baseline)
            self.assertTrue(any('fouten' in e.value for e in view.error))
            files['new'] = None
            view.run(timeout=60)
            self.assertNotIn('frame_new', view.session_state[CACHE_KEY])
            self.assertNotIn('products_new', view.session_state[CACHE_KEY])
            self.assertEqual(len(view.exception), 0)

    def test_mapping_change_revalidates_and_compares_without_reading_files_again(self):
        with patch('converter.read_supplier_file', wraps=converter.read_supplier_file) as read, \
             patch('converter.convert_products', wraps=converter.convert_products) as validate, \
             patch('comparison.compare_products', wraps=comparison.compare_products) as compare:
            view = app()
            title = next(w for w in view.selectbox if w.key and w.key.startswith('mapping_old_') and w.key.endswith('_Title'))
            title.set_value('Brand').run(timeout=60)
            self.assertEqual((read.call_count, validate.call_count, compare.call_count), (2, 3, 2))
            self.assertGreater(int(view.metric[-1].value), 5)
            view.selectbox(key='language').set_value('Nederlands').run(timeout=60)
            self.assertEqual((read.call_count, validate.call_count, compare.call_count), (2, 3, 2))
            title = next(w for w in view.selectbox if w.key and w.key.startswith('mapping_old_') and w.key.endswith('_Title'))
            title.set_value('SKU').run(timeout=60)
            self.assertEqual(len(view.metric), 0)
            self.assertNotIn('products_old', view.session_state[CACHE_KEY])
            self.assertNotIn('comparison', view.session_state[CACHE_KEY])

    def test_encoding_and_separator_changes_invalidate_the_affected_file(self):
        files = {'old': ('same.csv', CSV), 'new': ('same.csv', CSV)}
        with patch('streamlit.file_uploader', side_effect=uploader_for(files)), \
             patch('converter.read_supplier_file', wraps=converter.read_supplier_file) as read:
            view = app()
            view.radio(key='source_mode').set_value('upload').run(timeout=60)
            read.reset_mock()
            view.selectbox(key='encoding_old').set_value('Windows-1252').run(timeout=60)
            self.assertEqual(read.call_count, 1)
            self.assertEqual(view.metric[-1].value, '0')
            view.selectbox(key='separator_old').set_value(';').run(timeout=60)
            self.assertEqual(read.call_count, 2)
            self.assertEqual(len(view.metric), 0)
            self.assertNotIn('comparison', view.session_state[CACHE_KEY])
            view.selectbox(key='separator_old').set_value(None).run(timeout=60)
            self.assertEqual(read.call_count, 3)
            self.assertEqual(view.metric[-1].value, '0')

    def test_excel_sheet_names_are_reused_and_sheet_changes_recompute_results(self):
        workbook = Workbook()
        workbook.active.title = 'First'
        for sheet, price in ((workbook.active, 12.95), (workbook.create_sheet('Second'), 17.95)):
            sheet.append(['name', 'sku', 'price', 'stock'])
            sheet.append(['Cup', '000101', price, 10])
        buffer = BytesIO(); workbook.save(buffer); workbook.close()
        files = {side: ('same.xlsx', buffer.getvalue()) for side in ('old', 'new')}
        with patch('streamlit.file_uploader', side_effect=uploader_for(files)), \
             patch('converter.excel_sheet_names', wraps=converter.excel_sheet_names) as sheets, \
             patch('converter.read_supplier_file', wraps=converter.read_supplier_file) as read:
            view = app()
            view.radio(key='source_mode').set_value('upload').run(timeout=60)
            baseline = (sheets.call_count, read.call_count)
            self.assertEqual(sheets.call_count, 2)
            view.selectbox(key='language').set_value('Nederlands').run(timeout=60)
            self.assertEqual((sheets.call_count, read.call_count), baseline)
            view.selectbox(key='sheet_old').set_value('Second').run(timeout=60)
            self.assertEqual(sheets.call_count, 2)
            self.assertEqual(read.call_count, baseline[1] + 1)
            self.assertEqual(view.dataframe[-1].value['Oude waarde'].iloc[0], '17.95')
            self.assertEqual(view.dataframe[-1].value['Nieuwe waarde'].iloc[0], '12.95')

    def test_two_visitors_process_identical_uploads_independently(self):
        files = {'old': ('same.csv', CSV), 'new': ('same.csv', CSV)}
        with patch('streamlit.file_uploader', side_effect=uploader_for(files)), \
             patch('converter.read_supplier_file', wraps=converter.read_supplier_file) as read:
            first = app()
            first.radio(key='source_mode').set_value('upload').run(timeout=60)
            before = read.call_count
            second = app()
            second.radio(key='source_mode').set_value('upload').run(timeout=60)
            self.assertEqual(read.call_count, before + 4)
            a = first.session_state[CACHE_KEY]['frame_old']['value']
            b = second.session_state[CACHE_KEY]['frame_old']['value']
            self.assertIsNot(a, b)
            a.loc[0, 'name'] = 'Private edit'
            self.assertEqual(b.loc[0, 'name'], 'Cup')


if __name__ == '__main__':
    unittest.main()
