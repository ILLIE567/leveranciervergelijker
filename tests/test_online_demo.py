import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

from comparison import compare_products
from converter import FIELDS, convert_products, csv_bytes, read_supplier_file, suggest_mapping
from profiles import MAX_PROFILE_BYTES, PROFILE_KEY, decode_profiles, encode_profiles, get_profiles, save_profile

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "sample_data"
MAPPING = dict(zip(FIELDS, ("Omschrijving", "Artikelnummer", "Verkoopprijs", "Voorraad")))


def products(name):
    source = read_supplier_file((SAMPLES / name).read_bytes(), name)
    output, errors = convert_products(source, suggest_mapping(source.columns))
    if not errors.empty:
        raise ValueError("Het testbestand bevat fouten.")
    return output


class ComparisonTests(unittest.TestCase):
    def test_twenty_products_and_exactly_five_expected_changes(self):
        old, new = products("leverancier_oud.csv"), products("leverancier_nieuw.csv")
        self.assertEqual((len(old), len(new)), (20, 20))
        report = compare_products(old, new)
        self.assertEqual(report[["SKU", "Wijziging"]].values.tolist(), [
            ["000101", "Prijs gewijzigd"],
            ["000102", "Voorraad gewijzigd (uitverkocht)"],
            ["000103", "Naam gewijzigd"],
            ["000121", "Nieuw product"],
            ["000104", "Ontbreekt in nieuw bestand"],
        ])
        self.assertEqual(report.iloc[0][["Oude waarde", "Nieuwe waarde"]].tolist(), ["12.95", "15.95"])
        reopened = pd.read_csv(BytesIO(csv_bytes(report)), dtype=str, keep_default_na=False)
        pd.testing.assert_frame_equal(reopened, report, check_dtype=False)

    def test_identical_and_equivalent_decimal_notation_are_unchanged(self):
        old = products("leverancier_oud.csv")
        new = old.copy()
        new.loc[0, "Variant Price"] = "12,95"
        self.assertTrue(compare_products(old, new).empty)

    def test_changed_sku_is_visible_as_new_and_missing_without_changing_sources(self):
        old = products("01_correct.csv")
        new = old.copy()
        new.loc[0, "Variant SKU"] = "A-001"
        before = old.copy(deep=True)
        report = compare_products(old, new)
        self.assertEqual(report["Wijziging"].tolist(), ["Nieuw product", "Ontbreekt in nieuw bestand"])
        pd.testing.assert_frame_equal(old, before)

    def test_invalid_or_empty_input_never_produces_a_changes_report(self):
        good = products("01_correct.csv")
        duplicate = pd.concat([good, good.iloc[:1]], ignore_index=True)
        invalid_price = good.copy()
        invalid_price.loc[0, "Variant Price"] = "gratis"
        for bad in (duplicate, invalid_price, good.iloc[:0]):
            for old, new in ((bad, good), (good, bad)):
                with self.subTest(rows=len(bad)), self.assertRaises(ValueError):
                    compare_products(old, new)


class ProfileTests(unittest.TestCase):
    def test_two_visitors_do_not_share_profiles_or_later_edits(self):
        visitor_a, visitor_b = {}, {}
        save_profile(visitor_a, "Mijn leverancier", MAPPING)
        self.assertEqual(get_profiles(visitor_b), {})
        visitor_a[PROFILE_KEY]["Mijn leverancier"]["Title"] = "Naam"
        self.assertEqual(get_profiles(visitor_b), {})
        self.assertEqual(MAPPING["Title"], "Omschrijving")

    def test_download_and_restore_preserve_unicode_and_column_mappings(self):
        first, second = {}, {}
        save_profile(first, "Café leverancier", MAPPING)
        second[PROFILE_KEY] = decode_profiles(encode_profiles(get_profiles(first)))
        self.assertEqual(get_profiles(first), get_profiles(second))
        second[PROFILE_KEY]["Café leverancier"]["Title"] = "Naam"
        self.assertEqual(first[PROFILE_KEY]["Café leverancier"]["Title"], "Omschrijving")

    def test_existing_profile_requires_explicit_overwrite(self):
        state = {}
        save_profile(state, "Demo", MAPPING)
        changed = {**MAPPING, "Title": "Naam"}
        with self.assertRaises(ValueError):
            save_profile(state, "Demo", changed)
        self.assertEqual(state[PROFILE_KEY]["Demo"], MAPPING)
        save_profile(state, "Demo", changed, overwrite=True)
        self.assertEqual(state[PROFILE_KEY]["Demo"], changed)

    def test_invalid_imports_do_not_replace_current_profiles(self):
        state = {}
        save_profile(state, "Demo", MAPPING)
        invalid = (
            b"not json", b"[]", b'{"Demo": {}}',
            b'{"Demo":{"Title":"same","Variant SKU":"same","Variant Price":"same","Variant Inventory Qty":"same"}}',
            b"x" * (MAX_PROFILE_BYTES + 1),
        )
        for payload in invalid:
            with self.subTest(payload=payload[:20]), self.assertRaises(ValueError):
                decoded = decode_profiles(payload)
                state[PROFILE_KEY] = decoded
            self.assertEqual(get_profiles(state), {"Demo": MAPPING})


class PublicAppTests(unittest.TestCase):
    def test_demo_loads_and_computes_five_changes(self):
        app = AppTest.from_file(str(ROOT / "streamlit_app.py")).run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual([metric.value for metric in app.metric], ["20", "20", "5"])
        self.assertEqual(len(app.dataframe[-1].value), 5)

    def test_each_app_session_has_independent_saved_profiles(self):
        first = AppTest.from_file(str(ROOT / "streamlit_app.py")).run(timeout=30)
        first.text_input[0].set_value("Mijn leverancier").run(timeout=30)
        first.button(key="save_profile_old").click().run(timeout=30)
        self.assertEqual(len(first.exception), 0)
        self.assertIn("Mijn leverancier", first.session_state[PROFILE_KEY])
        first.selectbox(key="supplier_new").set_value("Mijn leverancier").run(timeout=30)
        self.assertEqual(len(first.exception), 0)
        self.assertEqual(first.metric[-1].value, "5")
        second = AppTest.from_file(str(ROOT / "streamlit_app.py")).run(timeout=30)
        self.assertEqual(len(second.exception), 0)
        self.assertEqual(second.session_state[PROFILE_KEY], {})
        self.assertNotIn("Mijn leverancier", second.selectbox(key="supplier_old").options)
        self.assertFalse((ROOT / "leveranciers.json").exists())

    def test_missing_saved_columns_block_comparison_instead_of_using_another_column(self):
        app = AppTest.from_file(str(ROOT / "streamlit_app.py")).run(timeout=30)
        app.session_state[PROFILE_KEY] = {"Andere indeling": {**MAPPING, "Title": "Oude kolomnaam"}}
        app.run(timeout=30)
        app.selectbox(key="supplier_old").set_value("Andere indeling").run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("Oude kolomnaam" in warning.value for warning in app.warning))
        self.assertEqual(len(app.metric), 0)

    def test_valid_csv_and_excel_uploads_produce_unchanged_report(self):
        for filename in ("01_correct.csv", "06_correct.xlsx"):
            def uploader(*args, **kwargs):
                if kwargs.get("key") in ("upload_old", "upload_new"):
                    file = BytesIO((SAMPLES / filename).read_bytes())
                    file.name = filename
                    return file
                return None

            with self.subTest(filename=filename), patch("streamlit.file_uploader", side_effect=uploader):
                app = AppTest.from_file(str(ROOT / "streamlit_app.py")).run(timeout=30)
                app.radio(key="source_mode").set_value("Eigen bestanden").run(timeout=30)
                self.assertEqual(len(app.exception), 0)
                self.assertEqual([metric.value for metric in app.metric], ["3", "3", "0"])

    def test_invalid_upload_blocks_changes_download_and_keeps_error_report(self):
        def uploader(*args, **kwargs):
            key = kwargs.get("key")
            if key not in ("upload_old", "upload_new"):
                return None
            filename = "01_correct.csv" if key == "upload_old" else "04_sku_fouten.csv"
            file = BytesIO((SAMPLES / filename).read_bytes())
            file.name = filename
            return file

        with patch("streamlit.file_uploader", side_effect=uploader), patch(
            "streamlit.download_button", wraps=st.download_button
        ) as downloads:
            app = AppTest.from_file(str(ROOT / "streamlit_app.py")).run(timeout=30)
            downloads.reset_mock()
            app.radio(key="source_mode").set_value("Eigen bestanden").run(timeout=30)
            self.assertEqual(len(app.exception), 0)
            self.assertTrue(any("3 fouten" in error.value for error in app.error))
            labels = [call.args[0] for call in downloads.call_args_list]
            self.assertIn("Download foutenrapport", labels)
            self.assertNotIn("Download veranderingenrapport", labels)


if __name__ == "__main__":
    unittest.main()
