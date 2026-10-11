# English supplier-file test samples

All products are fictional. Each old/new pair contains 100 products and nine
columns. CSV and Excel contain the same product data. Product codes are stored
as text, including their leading zeros.

## Files

- supplier_old.csv: the old supplier list.
- supplier_new.csv: the updated supplier list.
- supplier_old.xlsx: the old list as an Excel workbook.
- supplier_new.xlsx: the updated list as an Excel workbook.

The Excel workbooks have one worksheet named Products. All column headers,
product names, descriptions, categories and colour names are in English.

## How to test

1. Open the comparison app and select Your own files.
2. Upload supplier_old.csv on the left and supplier_new.csv on the right.
   You can also use the matching Excel pair.
3. Check the column mappings: Product name, SKU, Price and Stock.
4. Check that both files show 100 products and that the report has five changes.
5. Download the changes report and check the rows below.

Price is a fictional retail price. Both files use the same price basis. This
sample makes no claim about VAT or currency. Extra columns are deliberately
included to show that files can contain more information than the four fields
used in the comparison.

## Expected changes

| SKU | Product | Change | Old value | New value |
| --- | --- | --- | --- | --- |
| 000101 | Ceramic mug | Price changed | 12.95 | 15.95 |
| 000102 | Ballpoint pen | Stock changed (out of stock) | 20 | 0 |
| 000103 | A5 hardcover notebook | Name changed | A5 notebook | A5 hardcover notebook |
| 000201 | Cable organiser | New product | | Cable organiser |
| 000104 | Desk lamp | Missing from new file | Desk lamp | |

The app reports a missing product for review. It does not change a webshop.
The older Dutch fixtures are retained for the existing automated tests; the
public sample demo uses the English 100-product CSV files.
