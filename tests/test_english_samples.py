import unittest
from pathlib import Path

import pandas as pd

from comparison import compare_products
from converter import FIELDS, convert_products, read_supplier_file, suggest_mapping
from localization import localize_report

SAMPLES = Path(__file__).resolve().parents[1] / "sample_data"
HEADERS = ["SKU", "Product name", "Price", "Stock", "Brand", "Colour", "Weight (g)", "Description", "Category"]


class EnglishSampleTests(unittest.TestCase):
    def test_csv_and_excel_have_one_hundred_products_and_the_same_five_changes(self):
        pairs = {}
        for extension in ("csv", "xlsx"):
            products = []
            for version in ("old", "new"):
                filename = f"supplier_{version}.{extension}"
                frame = read_supplier_file((SAMPLES / filename).read_bytes(), filename)
                self.assertEqual(frame.columns.tolist(), HEADERS)
                self.assertEqual(len(frame), 100)
                mapping = suggest_mapping(frame.columns)
                self.assertEqual(mapping, dict(zip(FIELDS, ("Product name", "SKU", "Price", "Stock"))))
                clean, errors = convert_products(frame, mapping)
                self.assertTrue(errors.empty)
                self.assertEqual(clean["Variant SKU"].nunique(), 100)
                self.assertEqual(clean["Variant SKU"].iloc[0], "000101")
                self.assertTrue(frame["Description"].str.startswith("Fictional").all())
                products.append(clean)
            old, new = products
            report = localize_report(compare_products(old, new), "en")
            self.assertEqual(report.values.tolist(), [
                ["000101", "Ceramic mug", "Price changed", "12.95", "15.95"],
                ["000102", "Ballpoint pen", "Stock changed (out of stock)", "20", "0"],
                ["000103", "A5 hardcover notebook", "Name changed", "A5 notebook", "A5 hardcover notebook"],
                ["000201", "Cable organiser", "New product", "", "Cable organiser"],
                ["000104", "Desk lamp", "Missing from new file", "Desk lamp", ""],
            ])
            pairs[extension] = products
        for index in (0, 1):
            pd.testing.assert_frame_equal(pairs["csv"][index], pairs["xlsx"][index])


if __name__ == "__main__":
    unittest.main()
