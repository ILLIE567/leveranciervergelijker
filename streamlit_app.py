"""Openbare testversie; uploads en instellingen worden niet gedeeld."""

import hashlib
import json
from pathlib import Path

import streamlit as st

from comparison import compare_products
from converter import FIELDS, convert_products, csv_bytes, excel_sheet_names, read_supplier_file, suggest_mapping
from profiles import PROFILE_KEY, decode_profiles, encode_profiles, get_profiles, save_profile

ROOT = Path(__file__).resolve().parent
FEEDBACK_URL = "https://community.shopify.com/t/student-zoekt-webshopbeheerder-voor-test-met-leveranciersbestanden/695844"
LABELS = {
    "Title": "Productnaam",
    "Variant SKU": "Productcode (SKU)",
    "Variant Price": "Prijs",
    "Variant Inventory Qty": "Voorraad",
}


def profile_controls():
    with st.sidebar:
        st.header("Mijn leveranciersinstellingen")
        st.caption(
            "Instellingen blijven tijdens dit bezoek bewaard. "
            "Download ze om ze bij een volgend bezoek opnieuw te gebruiken."
        )
        uploaded = st.file_uploader(
            "Open mijn instellingenbestand", type=["json"], key="profile_upload"
        )
        replace = st.checkbox("Vervang mijn huidige instellingen", key="replace_profiles")
        if st.button("Instellingen laden", disabled=uploaded is None or not replace):
            try:
                st.session_state[PROFILE_KEY] = decode_profiles(uploaded.getvalue())
            except ValueError as error:
                st.error(str(error))
            else:
                for key in ("supplier_old", "supplier_new"):
                    st.session_state.pop(key, None)
                st.session_state["profile_notice"] = "Je leveranciersinstellingen zijn geladen."
                st.rerun()
        profiles = get_profiles(st.session_state)
        st.download_button(
            "Download mijn instellingen",
            encode_profiles(profiles),
            "mijn_leveranciers.json",
            "application/json",
            disabled=not profiles,
            key="download_profiles",
        )
        st.divider()
        st.subheader("Geef je mening")
        st.write("Klopt het rapport? Waar liep je vast? Zou dit je werk besparen?")
        st.link_button("Deel feedback op het forum", FEEDBACK_URL)


def upload_products(label, key, profiles, mode):
    st.subheader(label)
    if mode == "Oefenbestanden":
        filename = f"leverancier_{'oud' if key == 'old' else 'nieuw'}.csv"
        data = (ROOT / "sample_data" / filename).read_bytes()
        st.caption(f"Fictief voorbeeld: {filename}")
    else:
        uploaded = st.file_uploader(
            "Kies een CSV- of Excel-bestand", type=["csv", "xlsx"], key=f"upload_{key}"
        )
        if uploaded is None:
            return None
        filename, data = uploaded.name, uploaded.getvalue()

    delimiter, encoding, sheet = None, "utf-8-sig", None
    try:
        if filename.lower().endswith(".csv"):
            separators = {"Automatisch": None, "Puntkomma": ";", "Komma": ",", "Tab": "\t"}
            choice = st.selectbox("Scheidingsteken", list(separators), key=f"separator_{key}")
            delimiter = separators[choice]
            code = st.selectbox("Tekencodering", ["UTF-8", "Windows-1252"], key=f"encoding_{key}")
            encoding = "utf-8-sig" if code == "UTF-8" else "cp1252"
        else:
            sheet = st.selectbox("Werkblad", excel_sheet_names(data), key=f"sheet_{key}")
        frame = read_supplier_file(data, filename, delimiter=delimiter, encoding=encoding, sheet_name=sheet)
    except Exception as error:
        st.error(f"Bestand kon niet worden gelezen: {error}")
        return None

    st.write(f"{len(frame)} datarijen gevonden.")
    st.dataframe(frame.head(10).astype(str), hide_index=True)
    if frame.empty:
        st.warning("Het bestand bevat geen producten.")
        return None

    supplier = st.selectbox(
        "Kies een opgeslagen leverancier",
        [None] + sorted(profiles, key=str.casefold),
        format_func=lambda value: "Zelf instellen" if value is None else value,
        key=f"supplier_{key}",
    )
    saved = profiles[supplier] if supplier is not None else {}
    suggestions = suggest_mapping(frame.columns)
    options = [None] + list(frame.columns)
    missing = [saved[field] for field in FIELDS if supplier is not None and saved[field] not in frame.columns]
    if missing:
        st.warning("Opgeslagen kolommen ontbreken: " + ", ".join(missing) + ". Koppel die velden opnieuw.")

    fingerprint = hashlib.sha256(data + str((delimiter, encoding, sheet, mode)).encode()).hexdigest()[:16]
    token = hashlib.sha256(json.dumps([supplier, saved], sort_keys=True).encode()).hexdigest()[:16]
    mapping = {}
    st.write("Controleer de kolomkoppelingen:")
    for field in FIELDS:
        default = saved[field] if supplier is not None else suggestions.get(field)
        if default not in options:
            default = None
        mapping[field] = st.selectbox(
            LABELS[field],
            options,
            index=options.index(default),
            format_func=lambda value: "Kies een kolom" if value is None else value,
            key=f"mapping_{key}_{fingerprint}_{token}_{field}",
        )

    complete = all(value is not None for value in mapping.values())
    unique = complete and len(set(mapping.values())) == len(FIELDS)
    name_token = hashlib.sha256((supplier or "").encode()).hexdigest()[:16]
    with st.expander("Bewaar deze kolomkoppelingen"):
        name = st.text_input(
            "Naam van leverancier", value=supplier or "", max_chars=80,
            key=f"profile_name_{key}_{name_token}",
        ).strip()
        overwrite = False
        if name in profiles:
            overwrite = st.checkbox(f"Vervang de instellingen van '{name}'", key=f"overwrite_{key}_{name}")
        if st.button(
            "Instellingen bewaren", key=f"save_profile_{key}",
            disabled=not (name and complete and unique and (name not in profiles or overwrite)),
        ):
            try:
                save_profile(st.session_state, name, mapping, overwrite=overwrite)
            except ValueError as error:
                st.error(str(error))
            else:
                st.session_state["profile_notice"] = f"Instellingen van '{name}' bewaard tijdens dit bezoek."
                st.rerun()

    if not complete:
        st.warning("Koppel eerst alle vier velden.")
        return None
    if not unique:
        st.error("Kies voor ieder veld een verschillende kolom.")
        return None
    st.caption(
        f"Je vergelijkt de prijzen uit '{mapping['Variant Price']}'. "
        "Gebruik in beide bestanden dezelfde soort prijs en dezelfde btw-basis."
    )
    try:
        products, errors = convert_products(frame, mapping)
    except ValueError as error:
        st.error(str(error))
        return None
    if not errors.empty:
        st.error(f"{len(errors)} fouten. Los deze op voordat je vergelijkt.")
        st.dataframe(errors, hide_index=True)
        st.download_button("Download foutenrapport", csv_bytes(errors), f"foutenrapport_{key}.csv", "text/csv", key=f"errors_{key}")
        return None
    st.success("Bestand goedgekeurd.")
    return products


def main():
    st.set_page_config(page_title="Leveranciersbestanden vergelijken", page_icon="📋", layout="wide")
    st.title("Wat is er veranderd?")
    st.write("Vergelijk een oud en nieuw leveranciersbestand op productcode, naam, prijs en voorraad.")
    st.caption(
        "Openbare testversie. Uploads worden op de server verwerkt; de app schrijft ze niet naar bestanden. "
        "Gebruik voor deze test fictieve of geanonimiseerde productgegevens."
    )
    st.info(
        "Een gewijzigde productcode telt als een ontbrekend en een nieuw product. "
        "Ontbrekende producten worden alleen gemeld. Deze app past je webshop niet aan."
    )
    profile_controls()
    notice = st.session_state.pop("profile_notice", None)
    if notice:
        st.success(notice)
    profiles = get_profiles(st.session_state)
    mode = st.radio("Hoe wil je testen?", ["Oefenbestanden", "Eigen bestanden"], horizontal=True, key="source_mode")
    if mode == "Oefenbestanden":
        st.caption("De oefenbestanden bevatten ieder 20 producten en samen precies 5 veranderingen.")
        left_download, right_download = st.columns(2)
        for column, label, name in (
            (left_download, "Download oud oefenbestand", "leverancier_oud.csv"),
            (right_download, "Download nieuw oefenbestand", "leverancier_nieuw.csv"),
        ):
            with column:
                st.download_button(label, (ROOT / "sample_data" / name).read_bytes(), name, "text/csv", key=f"example_{name}")

    left, right = st.columns(2)
    with left:
        old = upload_products("1. Oud bestand", "old", profiles, mode)
    with right:
        new = upload_products("2. Nieuw bestand", "new", profiles, mode)
    if old is None or new is None:
        st.write("Gebruik twee foutvrije bestanden om te vergelijken.")
        return
    try:
        report = compare_products(old, new)
    except ValueError as error:
        st.error(str(error))
        return
    st.subheader("3. Veranderingen")
    columns = st.columns(3)
    for column, label, value in zip(columns, ("Producten oud", "Producten nieuw", "Veranderingen"), (len(old), len(new), len(report))):
        column.metric(label, value)
    if report.empty:
        st.success("Geen veranderingen gevonden.")
    else:
        st.dataframe(report, hide_index=True)
    st.caption(
        "Een product kan meerdere wijzigingen hebben. Productcodes worden exact vergeleken. "
        "Het veranderingenrapport is bedoeld om te controleren; een Shopify-importbestand is een aparte vervolgstap."
    )
    st.download_button("Download veranderingenrapport", csv_bytes(report), "veranderingenrapport.csv", "text/csv", key="download_changes")
    st.link_button("Vertel wat je van deze test vindt", FEEDBACK_URL)


if __name__ == "__main__":
    main()
