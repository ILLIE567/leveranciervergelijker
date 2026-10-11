import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

from comparison import compare_products
from converter import FIELDS, convert_products, csv_bytes, read_supplier_file, suggest_mapping
from localization import CHANGE_TEXT, localize_errors, localize_report, translate_error
from profiles import PROFILE_KEY

ROOT = Path(__file__).resolve().parents[1]


def sample_products(name):
    frame = read_supplier_file((ROOT / "sample_data" / name).read_bytes(), name)
    clean, errors = convert_products(frame, suggest_mapping(frame.columns))
    if not errors.empty:
        raise ValueError("Invalid fixture")
    return clean


class LanguageTests(unittest.TestCase):
    def test_translated_report_preserves_identifiers_values_and_original_frame(self):
        report = compare_products(sample_products("leverancier_oud.csv"), sample_products("leverancier_nieuw.csv"))
        original = report.copy(deep=True)
        english = localize_report(report, "en")
        self.assertEqual(english.columns.tolist(), ["SKU", "Product name", "Change", "Old value", "New value"])
        self.assertEqual(english["Change"].tolist(), ["Price changed", "Stock changed (out of stock)", "Name changed", "New product", "Missing from new file"])
        for old, new in (("SKU", "SKU"), ("Productnaam", "Product name"), ("Oude waarde", "Old value"), ("Nieuwe waarde", "New value")):
            self.assertEqual(report[old].tolist(), english[new].tolist())
        reopened = pd.read_csv(BytesIO(csv_bytes(english)), dtype=str, keep_default_na=False)
        self.assertEqual(reopened["SKU"].iloc[0], "000101")
        self.assertEqual(reopened["Old value"].iloc[0], "12.95")
        pd.testing.assert_frame_equal(report, original)
        pd.testing.assert_frame_equal(localize_report(report, "nl"), original)

    def test_english_errors_preserve_row_numbers_and_do_not_mutate_source(self):
        frame = read_supplier_file((ROOT / "sample_data" / "04_sku_fouten.csv").read_bytes(), "04_sku_fouten.csv")
        _, errors = convert_products(frame, suggest_mapping(frame.columns))
        original = errors.copy(deep=True)
        english = localize_errors(errors, "en")
        self.assertEqual(english.columns.tolist(), ["Row", "Error type", "Explanation"])
        self.assertEqual(english["Row"].tolist(), errors["Rijnummer"].tolist())
        self.assertIn("Missing sku", english["Error type"].tolist())
        self.assertIn("Duplicate SKU", english["Error type"].tolist())
        self.assertIn("SKU is missing.", english["Explanation"].tolist())
        pd.testing.assert_frame_equal(errors, original)
        pd.testing.assert_frame_equal(localize_errors(errors, "nl"), original)

    def test_file_reading_and_profile_errors_are_translated(self):
        examples = {
            "Excel-formule op A2. Vervang formules door vaste waarden in een kopie.": "Excel formula in A2. Replace formulas with fixed values in a copy.",
            "Excel-rij 17 bevat cellen buiten de kolomnamen. Geef elke kolom een naam.": "Excel row 17 contains cells beyond the column headers. Give every column a name.",
            "CSV-record 4: 5 velden, verwacht 4. Controleer scheidingstekens en quotes.": "CSV record 4: 5 fields, expected 4. Check the separators and quotation marks.",
            "Dit is geen geldig instellingenbestand in UTF-8.": "This is not a valid UTF-8 settings file.",
            "Prijs ontbreekt.": "Price is missing.",
            "Voorraad moet een geheel getal zijn.": "Stock must be a whole number.",
        }
        for dutch, english in examples.items():
            with self.subTest(message=dutch):
                self.assertEqual(translate_error(dutch), english)
                self.assertEqual(translate_error(dutch, "nl"), dutch)
        self.assertEqual(translate_error("Unknown external error"), "Unknown external error")

    def test_switching_language_updates_visible_report_and_download(self):
        with patch("streamlit.download_button", wraps=st.download_button) as downloads:
            app = AppTest.from_file(str(ROOT / "streamlit_app.py")).run(timeout=30)
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.title[0].value, "What has changed?")
            self.assertEqual(app.selectbox(key="language").value, "English")
            self.assertEqual([m.value for m in app.metric], ["100", "100", "5"])
            call = [c for c in downloads.call_args_list if c.kwargs.get("key") == "download_changes"][-1]
            english_csv = pd.read_csv(BytesIO(call.args[1]), dtype=str, keep_default_na=False)
            self.assertEqual(call.args[2], "changes_report.csv")
            self.assertEqual(english_csv["Change"].iloc[0], "Price changed")
            downloads.reset_mock()
            app.selectbox(key="language").set_value("Nederlands").run(timeout=30)
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.title[0].value, "Wat is er veranderd?")
            self.assertEqual([m.value for m in app.metric], ["100", "100", "5"])
            self.assertEqual(app.dataframe[-1].value["Wijziging"].iloc[0], "Prijs gewijzigd")
            call = [c for c in downloads.call_args_list if c.kwargs.get("key") == "download_changes"][-1]
            dutch_csv = pd.read_csv(BytesIO(call.args[1]), dtype=str, keep_default_na=False)
            self.assertEqual(call.args[2], "veranderingenrapport.csv")
            self.assertEqual(dutch_csv["SKU"].tolist(), english_csv["SKU"].tolist())
            app.selectbox(key="language").set_value("English").run(timeout=30)
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.dataframe[-1].value["Change"].iloc[0], "Price changed")

    def test_language_switch_keeps_mappings_supplier_names_and_mode(self):
        app = AppTest.from_file(str(ROOT / "streamlit_app.py")).run(timeout=30)
        title_mapping = next(widget for widget in app.selectbox if widget.key and widget.key.startswith("mapping_old_") and widget.key.endswith("_Title"))
        title_mapping.set_value("Brand").run(timeout=30)
        app.text_input[0].set_value("Café leverancier").run(timeout=30)
        app.button(key="save_profile_old").click().run(timeout=30)
        app.selectbox(key="supplier_old").set_value("Café leverancier").run(timeout=30)
        before = {name: mapping.copy() for name, mapping in app.session_state[PROFILE_KEY].items()}
        app.selectbox(key="language").set_value("Nederlands").run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.session_state[PROFILE_KEY], before)
        self.assertEqual(app.selectbox(key="supplier_old").value, "Café leverancier")
        title_mapping = next(widget for widget in app.selectbox if widget.key and widget.key.startswith("mapping_old_") and widget.key.endswith("_Title"))
        self.assertEqual(title_mapping.value, "Brand")
        app.radio(key="source_mode").set_value("upload").run(timeout=30)
        app.selectbox(key="language").set_value("English").run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.radio(key="source_mode").value, "upload")
        self.assertEqual(len(app.metric), 0)

    def test_english_invalid_upload_shows_english_error_table(self):
        def uploader(*args, **kwargs):
            if kwargs.get("key") not in ("upload_old", "upload_new"):
                return None
            file = BytesIO((ROOT / "sample_data" / "04_sku_fouten.csv").read_bytes())
            file.name = "04_sku_fouten.csv"
            return file

        with patch("streamlit.file_uploader", side_effect=uploader):
            app = AppTest.from_file(str(ROOT / "streamlit_app.py")).run(timeout=30)
            app.radio(key="source_mode").set_value("upload").run(timeout=30)
            self.assertEqual(len(app.exception), 0)
            self.assertTrue(any("3 errors" in error.value for error in app.error))
            self.assertEqual(app.dataframe[-1].value.columns.tolist(), ["Row", "Error type", "Explanation"])
            self.assertEqual(len(app.metric), 0)


if __name__ == "__main__":
    unittest.main()
