"""Vergelijk foutvrije leveranciersbestanden op hun exacte productcode."""

import pandas as pd

from converter import FIELDS, convert_products

REPORT_COLUMNS = ["SKU", "Productnaam", "Wijziging", "Oude waarde", "Nieuwe waarde"]


def compare_products(old_products, new_products):
    tables = []
    for label, products in (("oude", old_products), ("nieuwe", new_products)):
        clean, errors = convert_products(products, {field: field for field in FIELDS})
        if not errors.empty:
            raise ValueError(f"Het {label} bestand bevat fouten.")
        if clean.empty:
            raise ValueError(f"Het {label} bestand bevat geen producten.")
        tables.append(clean.set_index("Variant SKU"))

    old, new = tables
    changes = []
    for sku, product in new.iterrows():
        name = product["Title"]
        if sku not in old.index:
            changes.append([sku, name, "Nieuw product", "", name])
            continue
        previous = old.loc[sku]
        for field, change_type in (
            ("Title", "Naam gewijzigd"),
            ("Variant Price", "Prijs gewijzigd"),
            ("Variant Inventory Qty", "Voorraad gewijzigd"),
        ):
            before, after = previous[field], product[field]
            if before != after:
                if field == "Variant Inventory Qty" and int(before) > 0 and int(after) == 0:
                    change_type = "Voorraad gewijzigd (uitverkocht)"
                changes.append([sku, name, change_type, before, after])

    for sku, product in old.iterrows():
        if sku not in new.index:
            changes.append([sku, product["Title"], "Ontbreekt in nieuw bestand", product["Title"], ""])
    return pd.DataFrame(changes, columns=REPORT_COLUMNS, dtype=object)
