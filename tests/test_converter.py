"""Uitvoeren: python -m unittest discover -s tests -v"""

import hashlib
import re
import unittest
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile, ZIP_DEFLATED

import pandas as pd
from openpyxl import Workbook

from converter import (
    ERROR_COLUMNS, FIELDS, MAX_BYTES, convert_products, csv_bytes,
    excel_sheet_names, export_shopify, parse_number, read_supplier_file, suggest_mapping,
)

SAMPLES = Path(__file__).resolve().parents[1] / "sample_data"


def xlsx_bytes(rows, second_sheet=False):
    workbook = Workbook()
    for row in rows:
        workbook.active.append(row)
    if second_sheet:
        workbook.create_sheet("Extra").append(["name", "sku", "price", "stock"])
    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()


def convert_sample(filename):
    frame = read_supplier_file((SAMPLES / filename).read_bytes(), filename)
    return frame, *convert_products(frame, suggest_mapping(frame.columns))


class ConverterTests(unittest.TestCase):
    def test_incorrect_or_missing_excel_dimensions_never_hide_rows(self):
        original = xlsx_bytes([["name", "sku", "price", "stock"],
                               ["Mok", "001", 2, 3], ["Pen", "002", 4, 5]])
        for dimension in [b'<dimension ref="A1:A1"/>', b'', b'<dimension ref="A1:XFD1048576"/>']:
            with self.subTest(dimension=dimension):
                buffer = BytesIO()
                with ZipFile(BytesIO(original)) as source, ZipFile(buffer, "w", ZIP_DEFLATED) as target:
                    for item in source.infolist():
                        content = source.read(item.filename)
                        if item.filename == "xl/worksheets/sheet1.xml":
                            content = re.sub(rb'<dimension[^>]*/>', dimension, content)
                        target.writestr(item, content)
                frame = read_supplier_file(buffer.getvalue(), "dimensions.xlsx")
                self.assertEqual(len(frame), 2)
                self.assertEqual(frame["sku"].tolist(), ["001", "002"])

    def test_excel_error_cells_cannot_become_valid_skus(self):
        data = xlsx_bytes([["name", "sku", "price", "stock"], ["Mok", "#N/A", 2, 3]])
        with self.assertRaisesRegex(ValueError, "Excel-foutwaarde op B2"):
            read_supplier_file(data, "error.xlsx")

    def test_excel_short_rows_keep_missing_cells(self):
        data = xlsx_bytes([["name", "sku", "price", "stock"], ["Mok", "001"], ["Pen", "002", 4, 5]])
        frame = read_supplier_file(data, "short.xlsx")
        output, errors = convert_products(frame, suggest_mapping(frame.columns))
        self.assertEqual(len(output), 2)
        self.assertEqual(errors["Rijnummer"].tolist(), [2, 2])

    def test_row_and_column_limits_for_both_formats(self):
        excel = xlsx_bytes([["name", "sku", "price", "stock"], ["Mok", "001", 2, 3], ["Pen", "002", 4, 5]])
        csv = b"name,sku,price,stock\nMok,001,2,3\nPen,002,4,5\n"
        for data, filename in [(excel, "limit.xlsx"), (csv, "limit.csv")]:
            with self.subTest(filename=filename), patch("converter.MAX_ROWS", 1):
                with self.assertRaisesRegex(ValueError, "Maximaal 1 datarijen"):
                    read_supplier_file(data, filename)
            with self.subTest(filename=filename), patch("converter.MAX_COLUMNS", 3):
                with self.assertRaisesRegex(ValueError, "Maximaal 3 kolommen"):
                    read_supplier_file(data, filename)

    def test_excel_data_outside_headers_is_not_discarded(self):
        data = xlsx_bytes([["name", "sku"], ["Mok", "001", 2, 3]])
        with self.assertRaisesRegex(ValueError, "buiten de kolomnamen"):
            read_supplier_file(data, "extra.xlsx")

    def test_negative_zero_exports_as_zero(self):
        self.assertEqual(parse_number("-0.00", "Prijs"), "0.00")

    def test_correct_csv_dutch_comma_and_excel(self):
        for filename, rows in [("01_correct.csv", 3), ("02_nederlands.csv", 2),
                               ("03_kommaprijzen.csv", 3), ("06_correct.xlsx", 3)]:
            with self.subTest(filename=filename):
                frame, output, errors = convert_sample(filename)
                self.assertEqual(len(frame), rows)
                self.assertEqual(len(output), rows)
                self.assertTrue(errors.empty)
                self.assertTrue(set(FIELDS) <= set(output.columns))

    def test_price_normalization(self):
        for value, expected in [("12,95", "12.95"), ("12.95", "12.95"),
                                (12.95, "12.95"), (12, "12.00"), (0, "0.00"),
                                (" 2,50 ", "2.50")]:
            with self.subTest(value=value):
                self.assertEqual(parse_number(value, "Prijs"), expected)

    def test_invalid_prices_never_guessed_or_rounded(self):
        for value in ["", None, "gratis", "-1", "€12,95", "1,234", "1.000",
                      "1.234,56", "1,234.56", "1e3", "NaN", float("inf"), True]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_number(value, "Prijs")

    def test_inventory_normalization(self):
        for value, expected in [("5", "5"), (5.0, "5"), ("5,0", "5"), (0, "0")]:
            with self.subTest(value=value):
                self.assertEqual(parse_number(value, "Voorraad"), expected)

    def test_invalid_inventory(self):
        for value in ["", None, "-1", "2.5", "veel", True, "1e4", "1.000", "2,000"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_number(value, "Voorraad")

    def test_duplicate_and_missing_skus_all_occurrences(self):
        frame, output, report = convert_sample("04_sku_fouten.csv")
        self.assertEqual(len(frame), 4)
        self.assertEqual(len(output), 4)
        self.assertEqual(report.loc[report["Type fout"] == "Dubbele SKU", "Rijnummer"].tolist(), [2, 3])
        self.assertEqual(report.loc[report["Type fout"] == "Ontbrekende sku", "Rijnummer"].tolist(), [4])
        with self.assertRaisesRegex(ValueError, "geblokkeerd"):
            export_shopify(output, report)

    def test_multiple_errors_and_report_reopen(self):
        frame, output, report = convert_sample("05_meerdere_fouten.csv")
        self.assertEqual(len(frame), 8)
        self.assertEqual(len(output), 8)
        self.assertEqual(len(report), 10)
        self.assertEqual(report["Rijnummer"].tolist(), [2, 3, 4, 5, 6, 6, 6, 7, 7, 8])
        reopened = pd.read_csv(BytesIO(csv_bytes(report)))
        self.assertEqual(list(reopened.columns), ERROR_COLUMNS)
        pd.testing.assert_frame_equal(reopened, report)
        self.assertTrue(set(report["Type fout"]) >= {
            "Ontbrekende productnaam", "Ongeldige prijs", "Ongeldige voorraad", "Ontbrekende sku",
        })

    def test_export_reopen_preserves_skus_prices_and_rows(self):
        frame, output, report = convert_sample("01_correct.csv")
        reopened = pd.read_csv(BytesIO(export_shopify(output, report)), dtype=str, keep_default_na=False)
        pd.testing.assert_frame_equal(reopened, output, check_dtype=False)
        self.assertEqual(reopened["Variant SKU"].tolist(), frame["sku"].tolist())
        self.assertEqual(reopened["Variant SKU"][0], "000123")
        self.assertEqual(reopened["Variant Price"].tolist(), ["12.95", "4.50", "29.00"])
        self.assertTrue(reopened["Handle"].is_unique)
        self.assertEqual(reopened["Option1 Value"].tolist(), ["Default Title"] * 3)

    def test_manual_mapping_and_unique_columns(self):
        frame = pd.DataFrame([["Mok", "001", "12,95", "3"]], columns=["a", "b", "c", "d"])
        self.assertEqual(suggest_mapping(frame.columns), dict.fromkeys(FIELDS))
        output, report = convert_products(frame, dict(zip(FIELDS, frame.columns)))
        self.assertTrue(report.empty)
        self.assertEqual(output["Variant SKU"][0], "001")
        for mapping in [{}, dict.fromkeys(FIELDS, "a"), dict.fromkeys(FIELDS, "missing")]:
            with self.subTest(mapping=mapping), self.assertRaises(ValueError):
                convert_products(frame, mapping)

    def test_ambiguous_suggestion_is_empty(self):
        self.assertIsNone(suggest_mapping(["sku", "productcode"])["Variant SKU"])

    def test_excel_numeric_sku_blocked_and_text_preserved(self):
        data = xlsx_bytes([["name", "sku", "price", "stock"],
                           ["Mok", 123, 12.95, 2], ["Pen", "000123", 2, 3]])
        frame = read_supplier_file(data, "numeric.xlsx")
        output, report = convert_products(frame, suggest_mapping(frame.columns))
        self.assertIn("Ongeldige sku", report["Type fout"].tolist())
        self.assertEqual(output["Variant SKU"][1], "000123")

    def test_excel_formula_blocked(self):
        data = xlsx_bytes([["name", "sku", "price", "stock"], ["Mok", "001", "=1+1", 2]])
        with self.assertRaisesRegex(ValueError, "formule"):
            read_supplier_file(data, "formula.xlsx")

    def test_excel_multiple_sheets_explicit_selection(self):
        data = xlsx_bytes([["name", "sku", "price", "stock"], ["Mok", "001", 5, 2]], True)
        self.assertEqual(excel_sheet_names(data), ["Sheet", "Extra"])
        with self.assertRaisesRegex(ValueError, "Meerdere"):
            read_supplier_file(data, "sheets.xlsx")
        self.assertEqual(len(read_supplier_file(data, "sheets.xlsx", sheet_name="Sheet")), 1)

    def test_bad_csv_rejected(self):
        for data in [b"", b"name,sku\na,1,extra\n", b"name,name\na,b\n",
                     b"name,\na,b\n", b'name,sku\n"open,001\n']:
            with self.subTest(data=data), self.assertRaises(ValueError):
                read_supplier_file(data, "bad.csv", delimiter=",")

    def test_blank_rows_and_na_like_skus_preserved(self):
        data = b"name,sku,price,stock\nMok,NA,1,2\n\nPen,NULL,2,3\n"
        frame = read_supplier_file(data, "blank.csv", delimiter=",")
        output, report = convert_products(frame, suggest_mapping(frame.columns))
        self.assertEqual(len(frame), 3)
        self.assertEqual(len(output), 3)
        self.assertEqual(output["Variant SKU"].tolist(), ["NA", "", "NULL"])
        self.assertEqual(report["Rijnummer"].tolist(), [3] * 4)

    def test_encoding_quotes_and_leading_zero(self):
        data = 'name;sku;price;stock\n"Café, mok";001;12,95;1\n'.encode("cp1252")
        with self.assertRaisesRegex(ValueError, "Tekencodering"):
            read_supplier_file(data, "legacy.csv")
        frame = read_supplier_file(data, "legacy.csv", encoding="cp1252")
        self.assertEqual(frame.iloc[0].tolist(), ["Café, mok", "001", "12,95", "1"])

    def test_limits_wrong_extension_and_corrupt_excel(self):
        for data, name in [(b"x" * (MAX_BYTES + 1), "large.csv"),
                           (b"data", "file.xls"), (b"not excel", "file.xlsx")]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                read_supplier_file(data, name)

    def test_empty_export_blocked_and_empty_report_headers(self):
        columns = ["name", "sku", "price", "stock"]
        output, report = convert_products(pd.DataFrame(columns=columns), suggest_mapping(columns))
        with self.assertRaisesRegex(ValueError, "Geen producten"):
            export_shopify(output, report)
        self.assertEqual(csv_bytes(report).decode("utf-8-sig"), "Rijnummer,Type fout,Uitleg\n")

    def test_sku_whitespace_case_and_spreadsheet_injection(self):
        frame = pd.DataFrame([
            ["Mok", "abc", "1", "1"], ["Pen", "ABC ", "1", "1"],
            ["=1+1", "@cmd", "1", "1"],
        ], columns=["name", "sku", "price", "stock"])
        output, report = convert_products(frame, suggest_mapping(frame.columns))
        self.assertEqual(output["Variant SKU"].tolist(), ["abc", "ABC ", "@cmd"])
        self.assertEqual(len(report[report["Type fout"] == "Dubbele SKU"]), 2)
        self.assertIn("Spaties bij sku", report["Type fout"].tolist())
        self.assertIn("Onveilige sku", report["Type fout"].tolist())

    def test_full_local_file_flow_all_samples_originals_unchanged(self):
        for source in sorted(SAMPLES.glob("*")):
            with self.subTest(source=source.name), TemporaryDirectory() as temporary:
                before = hashlib.sha256(source.read_bytes()).digest()
                frame = read_supplier_file(source.read_bytes(), source.name)
                mapping = suggest_mapping(frame.columns)
                output, report = convert_products(frame, mapping)
                self.assertEqual(len(frame), len(output))
                report_path = Path(temporary) / "foutenrapport.csv"
                report_path.write_bytes(csv_bytes(report))
                self.assertEqual(len(pd.read_csv(report_path)), len(report))
                if report.empty:
                    download_path = Path(temporary) / "shopify_products.csv"
                    download_path.write_bytes(export_shopify(output, report))
                    reopened = pd.read_csv(download_path, dtype=str, keep_default_na=False)
                    pd.testing.assert_frame_equal(reopened, output, check_dtype=False)
                    self.assertEqual(reopened["Variant SKU"].tolist(), frame[mapping["Variant SKU"]].tolist())
                else:
                    with self.assertRaises(ValueError):
                        export_shopify(output, report)
                self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), before)


if __name__ == "__main__":
    unittest.main()
