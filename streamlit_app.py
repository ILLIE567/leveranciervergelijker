"""Public bilingual test app; uploads and settings stay within each session."""

import hashlib
import json
from pathlib import Path

import streamlit as st

from comparison import compare_products
from converter import FIELDS, convert_products, csv_bytes, excel_sheet_names, read_supplier_file, suggest_mapping
from localization import localize_errors, localize_report, translate_error
from profiles import PROFILE_KEY, decode_profiles, encode_profiles, get_profiles, save_profile

ROOT = Path(__file__).resolve().parent
FEEDBACK_URL = "https://community.shopify.com/t/student-zoekt-webshopbeheerder-voor-test-met-leveranciersbestanden/695844"
LABELS = {
    "Title": ("Productnaam", "Product name"),
    "Variant SKU": ("Productcode (SKU)", "Product code (SKU)"),
    "Variant Price": ("Prijs", "Price"),
    "Variant Inventory Qty": ("Voorraad", "Stock"),
}


def language():
    return "nl" if st.session_state.get("language") == "Nederlands" else "en"


def tr(dutch, english, **values):
    return (dutch if language() == "nl" else english).format(**values)


def show_error(error):
    st.error(translate_error(str(error), language()))


def profile_controls():
    with st.sidebar:
        st.header(tr("Mijn leveranciersinstellingen", "My supplier settings"))
        st.caption(tr(
            "Instellingen blijven tijdens dit bezoek bewaard. Download ze om ze bij een volgend bezoek opnieuw te gebruiken.",
            "Settings are kept during this visit. Download them to reuse them on your next visit.",
        ))
        uploaded = st.file_uploader(
            tr("Open mijn instellingenbestand", "Open my settings file"),
            type=["json"], key="profile_upload",
        )
        replace = st.checkbox(tr("Vervang mijn huidige instellingen", "Replace my current settings"), key="replace_profiles")
        if st.button(tr("Instellingen laden", "Load settings"), disabled=uploaded is None or not replace):
            try:
                st.session_state[PROFILE_KEY] = decode_profiles(uploaded.getvalue())
            except ValueError as error:
                show_error(error)
            else:
                for key in ("supplier_old", "supplier_new"):
                    st.session_state.pop(key, None)
                st.session_state["profile_notice"] = {"kind": "loaded"}
                st.rerun()
        profiles = get_profiles(st.session_state)
        st.download_button(
            tr("Download mijn instellingen", "Download my settings"),
            encode_profiles(profiles),
            tr("mijn_leveranciers.json", "my_suppliers.json"),
            "application/json", disabled=not profiles, key="download_profiles",
        )
        st.divider()
        st.subheader(tr("Geef je mening", "Share your feedback"))
        st.write(tr("Klopt het rapport? Waar liep je vast? Zou dit je werk besparen?", "Is the report correct? What was confusing? Would this save you time?"))
        st.link_button(tr("Deel feedback op het forum", "Share feedback on the forum"), FEEDBACK_URL)


def upload_products(label, key, profiles, mode):
    st.subheader(label)
    if mode == "demo":
        filename = f"leverancier_{'oud' if key == 'old' else 'nieuw'}.csv"
        data = (ROOT / "sample_data" / filename).read_bytes()
        st.caption(tr("Fictief voorbeeld: {name}", "Fictional sample: {name}", name=filename))
    else:
        uploaded = st.file_uploader(
            tr("Kies een CSV- of Excel-bestand", "Choose a CSV or Excel file"),
            type=["csv", "xlsx"], key=f"upload_{key}",
        )
        if uploaded is None:
            return None
        filename, data = uploaded.name, uploaded.getvalue()

    delimiter, encoding, sheet = None, "utf-8-sig", None
    try:
        if filename.lower().endswith(".csv"):
            separators = {
                None: tr("Automatisch", "Automatic"),
                ";": tr("Puntkomma", "Semicolon"),
                ",": tr("Komma", "Comma"),
                "\t": tr("Tab", "Tab"),
            }
            delimiter = st.selectbox(
                tr("Scheidingsteken", "Separator"), list(separators),
                format_func=lambda value: separators[value], key=f"separator_{key}",
            )
            code = st.selectbox(tr("Tekencodering", "Text encoding"), ["UTF-8", "Windows-1252"], key=f"encoding_{key}")
            encoding = "utf-8-sig" if code == "UTF-8" else "cp1252"
        else:
            sheet = st.selectbox(tr("Werkblad", "Worksheet"), excel_sheet_names(data), key=f"sheet_{key}")
        frame = read_supplier_file(data, filename, delimiter=delimiter, encoding=encoding, sheet_name=sheet)
    except Exception as error:
        st.error(tr("Bestand kon niet worden gelezen: {error}", "Could not read the file: {error}", error=translate_error(str(error), language())))
        return None

    st.write(tr("{count} datarijen gevonden.", "{count} data rows found.", count=len(frame)))
    st.dataframe(frame.head(10).astype(str), hide_index=True)
    if frame.empty:
        st.warning(tr("Het bestand bevat geen producten.", "The file contains no products."))
        return None

    manual_label = tr("Zelf instellen", "Set up manually")
    supplier = st.selectbox(
        tr("Kies een opgeslagen leverancier", "Choose a saved supplier"),
        [None] + sorted(profiles, key=str.casefold),
        format_func=lambda value: manual_label if value is None else value,
        key=f"supplier_{key}",
    )
    saved = profiles[supplier] if supplier is not None else {}
    suggestions = suggest_mapping(frame.columns)
    options = [None] + list(frame.columns)
    missing = [saved[field] for field in FIELDS if supplier is not None and saved[field] not in frame.columns]
    if missing:
        st.warning(tr("Opgeslagen kolommen ontbreken: {columns}. Koppel die velden opnieuw.", "Saved columns are missing: {columns}. Map these fields again.", columns=", ".join(missing)))

    fingerprint = hashlib.sha256(data + str((delimiter, encoding, sheet, mode)).encode()).hexdigest()[:16]
    token = hashlib.sha256(json.dumps([supplier, saved], sort_keys=True).encode()).hexdigest()[:16]
    mapping = {}
    st.write(tr("Controleer de kolomkoppelingen:", "Check the column mappings:"))
    column_prompt = tr("Kies een kolom", "Choose a column")
    for field in FIELDS:
        default = saved[field] if supplier is not None else suggestions.get(field)
        if default not in options:
            default = None
        mapping[field] = st.selectbox(
            tr(*LABELS[field]), options, index=options.index(default),
            format_func=lambda value: column_prompt if value is None else value,
            key=f"mapping_{key}_{fingerprint}_{token}_{field}",
        )

    complete = all(value is not None for value in mapping.values())
    unique = complete and len(set(mapping.values())) == len(FIELDS)
    name_token = hashlib.sha256((supplier or "").encode()).hexdigest()[:16]
    with st.expander(tr("Bewaar deze kolomkoppelingen", "Save these column mappings")):
        name = st.text_input(
            tr("Naam van leverancier", "Supplier name"), value=supplier or "", max_chars=80,
            key=f"profile_name_{key}_{name_token}",
        ).strip()
        overwrite = False
        if name in profiles:
            overwrite = st.checkbox(tr("Vervang de instellingen van '{name}'", "Replace the settings for '{name}'", name=name), key=f"overwrite_{key}_{name}")
        if st.button(
            tr("Instellingen bewaren", "Save settings"), key=f"save_profile_{key}",
            disabled=not (name and complete and unique and (name not in profiles or overwrite)),
        ):
            try:
                save_profile(st.session_state, name, mapping, overwrite=overwrite)
            except ValueError as error:
                show_error(error)
            else:
                st.session_state["profile_notice"] = {"kind": "saved", "name": name}
                st.rerun()

    if not complete:
        st.warning(tr("Koppel eerst alle vier velden.", "Map all four fields first."))
        return None
    if not unique:
        st.error(tr("Kies voor ieder veld een verschillende kolom.", "Choose a different column for each field."))
        return None
    st.caption(tr(
        "Je vergelijkt de prijzen uit '{column}'. Gebruik in beide bestanden dezelfde soort prijs en dezelfde btw-basis.",
        "You are comparing prices from '{column}'. Use the same price type and VAT basis in both files.",
        column=mapping["Variant Price"],
    ))
    try:
        products, errors = convert_products(frame, mapping)
    except ValueError as error:
        show_error(error)
        return None
    if not errors.empty:
        st.error(tr("{count} fouten. Los deze op voordat je vergelijkt.", "{count} errors. Fix them before comparing.", count=len(errors)))
        display_errors = localize_errors(errors, language())
        st.dataframe(display_errors, hide_index=True)
        st.download_button(tr("Download foutenrapport", "Download error report"), csv_bytes(display_errors), tr("foutenrapport_{key}.csv", "error_report_{key}.csv", key=key), "text/csv", key=f"errors_{key}")
        return None
    st.success(tr("Bestand goedgekeurd.", "File validated."))
    return products


def main():
    st.set_page_config(page_title="Supplier file comparison", page_icon="🔎", layout="wide")
    st.sidebar.selectbox("Language / Taal", ["English", "Nederlands"], key="language")
    st.title(tr("Wat is er veranderd?", "What has changed?"))
    st.write(tr("Vergelijk een oud en nieuw leveranciersbestand op productcode, naam, prijs en voorraad.", "Compare old and new supplier files by product code, name, price and stock."))
    st.caption(tr(
        "Openbare testversie. Uploads worden op de server verwerkt; de app schrijft ze niet naar bestanden. Gebruik voor deze test fictieve of geanonimiseerde productgegevens.",
        "Public test version. Uploads are processed on the server; the app does not write them to files. Use fictional or anonymized product data for this test.",
    ))
    st.info(tr(
        "Een gewijzigde productcode telt als een ontbrekend en een nieuw product. Ontbrekende producten worden alleen gemeld. Deze app past je webshop niet aan.",
        "A changed product code counts as a missing product and a new product. Missing products are only reported. This app does not modify your store.",
    ))
    profile_controls()
    notice = st.session_state.pop("profile_notice", None)
    if notice:
        if notice["kind"] == "loaded":
            st.success(tr("Je leveranciersinstellingen zijn geladen.", "Your supplier settings have been loaded."))
        else:
            st.success(tr("Instellingen van '{name}' bewaard tijdens dit bezoek.", "Settings for '{name}' saved for this visit.", name=notice["name"]))
    profiles = get_profiles(st.session_state)
    modes = {"demo": tr("Oefenbestanden", "Sample files"), "upload": tr("Eigen bestanden", "Your own files")}
    mode = st.radio(tr("Hoe wil je testen?", "How would you like to test?"), list(modes), format_func=lambda value: modes[value], horizontal=True, key="source_mode")
    if mode == "demo":
        st.caption(tr("De oefenbestanden bevatten ieder 20 producten en samen precies 5 veranderingen.", "Each sample file contains 20 products, with exactly 5 changes between the files."))
        left_download, right_download = st.columns(2)
        for column, label, name in (
            (left_download, ("Download oud oefenbestand", "Download old sample file"), "leverancier_oud.csv"),
            (right_download, ("Download nieuw oefenbestand", "Download new sample file"), "leverancier_nieuw.csv"),
        ):
            with column:
                st.download_button(tr(*label), (ROOT / "sample_data" / name).read_bytes(), name, "text/csv", key=f"example_{name}")

    left, right = st.columns(2)
    with left:
        old = upload_products(tr("1. Oud bestand", "1. Old file"), "old", profiles, mode)
    with right:
        new = upload_products(tr("2. Nieuw bestand", "2. New file"), "new", profiles, mode)
    if old is None or new is None:
        st.write(tr("Gebruik twee foutvrije bestanden om te vergelijken.", "Use two files without errors to compare."))
        return
    try:
        report = compare_products(old, new)
    except ValueError as error:
        show_error(error)
        return
    st.subheader(tr("3. Veranderingen", "3. Changes"))
    columns = st.columns(3)
    labels = (("Producten oud", "Old products"), ("Producten nieuw", "New products"), ("Veranderingen", "Changes"))
    for column, label, value in zip(columns, labels, (len(old), len(new), len(report))):
        column.metric(tr(*label), value)
    display_report = localize_report(report, language())
    if report.empty:
        st.success(tr("Geen veranderingen gevonden.", "No changes found."))
    else:
        st.dataframe(display_report, hide_index=True)
    st.caption(tr(
        "Een product kan meerdere wijzigingen hebben. Productcodes worden exact vergeleken. Het veranderingenrapport is bedoeld om te controleren; een Shopify-importbestand is een aparte vervolgstap.",
        "A product can have several changes. Product codes are matched exactly. This report is for reviewing changes; a Shopify import file is a separate next step.",
    ))
    st.download_button(tr("Download veranderingenrapport", "Download changes report"), csv_bytes(display_report), tr("veranderingenrapport.csv", "changes_report.csv"), "text/csv", key="download_changes")
    st.link_button(tr("Vertel wat je van deze test vindt", "Tell us what you think of this test"), FEEDBACK_URL)


if __name__ == "__main__":
    main()
