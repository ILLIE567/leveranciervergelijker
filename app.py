"""Start met: python -m streamlit run app.py"""

import hashlib

import streamlit as st

from converter import (
    FIELDS, convert_products, csv_bytes, excel_sheet_names,
    export_shopify, read_supplier_file, suggest_mapping,
)


def main():
    st.set_page_config(page_title="Leverancier naar Shopify", page_icon="📦", layout="wide")
    st.title("Leverancier → Shopify CSV")
    st.write("Upload een bestand, controleer de kolomkoppeling en download een gecontroleerde CSV.")
    st.caption("Alles blijft lokaal. Eén rij = één los product. Geen verbinding met een Shopify-winkel.")
    st.info("Deze MVP maakt bestanden voor nieuwe losse producten met één voorraadlocatie. Gebruik de export niet om bestaande producten of varianten bij te werken.")
    st.subheader("1. Upload je leveranciersbestand")
    uploaded = st.file_uploader("CSV of Excel, maximaal 10 MB", type=["csv", "xlsx"])
    if uploaded is None:
        st.write("Probeer eerst een fictief bestand uit de map sample_data.")
        return
    data = uploaded.getvalue()
    sheet = None
    delimiter = None
    encoding = "utf-8-sig"
    try:
        if uploaded.name.lower().endswith(".csv"):
            left, right = st.columns(2)
            separator = left.selectbox("Scheidingsteken", ["Automatisch", "Puntkomma (;)", "Komma (,)", "Tab"])
            delimiter = {"Automatisch": None, "Puntkomma (;)": ";", "Komma (,)": ",", "Tab": "\t"}[separator]
            encoding_label = right.selectbox("Tekencodering", ["UTF-8", "Windows-1252"])
            encoding = "utf-8-sig" if encoding_label == "UTF-8" else "cp1252"
        else:
            sheets = excel_sheet_names(data)
            sheet = st.selectbox("Werkblad", sheets)
        frame = read_supplier_file(data, uploaded.name, delimiter, encoding, sheet)
    except Exception as exc:
        st.error(f"Bestand kon niet worden gelezen: {exc}")
        return
    st.write(f"Gevonden: **{len(frame)} datarijen** en **{len(frame.columns)} kolommen**.")
    st.write("Kolommen: " + ", ".join(frame.columns))
    preview = frame.head(10).copy()
    preview.index = range(2, len(preview) + 2)
    preview.index.name = "Rijnummer"
    st.dataframe(preview.astype(str), width="stretch")
    st.caption("Rijnummer: kopregel = 1, eerste datarij = 2. Bij CSV met regeleinden in quotes tellen we records, niet fysieke tekstregels.")
    if frame.empty:
        st.warning("Het bestand bevat alleen kolomnamen, geen producten.")
        return
    st.subheader("2. Controleer de kolomkoppeling")
    st.write("Suggesties zijn alleen een startpunt. Kies voor elk veld de juiste bronkolom.")
    suggestions = suggest_mapping(frame.columns)
    options = [None] + list(frame.columns)
    fingerprint = hashlib.sha256(data + str((sheet, delimiter, encoding)).encode()).hexdigest()[:16]
    mapping = {}
    for field in FIELDS:
        mapping[field] = st.selectbox(
            field, options, index=options.index(suggestions[field]),
            format_func=lambda value: "— Kies een kolom —" if value is None else value,
            key=f"mapping_{fingerprint}_{field}",
        )
    if any(value is None for value in mapping.values()):
        st.warning("Koppel eerst alle vier velden.")
        return
    try:
        output, report = convert_products(frame, mapping)
    except ValueError as exc:
        st.error(str(exc))
        return
    st.subheader("3. Bekijk de controles")
    left, middle, right = st.columns(3)
    left.metric("Ingelezen rijen", len(frame))
    middle.metric("Rijen in resultaat", len(output))
    right.metric("Fouten", len(report))
    st.caption("Prijzen: komma of punt, maximaal twee decimalen, geen duizendtallen of valuta. Voorraad: geheel getal ≥ 0. SKU's blijven tekst, inclusief voorloopnullen; numerieke Excel-SKU's worden geblokkeerd.")
    if not report.empty:
        st.error(f"{len(report)} fouten in {report['Rijnummer'].nunique()} rijen. Shopify-download is geblokkeerd. Verbeter een kopie van het bronbestand en upload die opnieuw.")
        st.dataframe(report, hide_index=True, width="stretch")
    else:
        st.success("Alle rijen zijn goedgekeurd. Geen rijen verwijderd.")
    st.download_button("Download foutenrapport", csv_bytes(report), "foutenrapport.csv", "text/csv", key="report_download")
    st.subheader("4. Controleer en download")
    st.dataframe(output, hide_index=True, width="stretch")
    with st.expander("Wat verandert er bij de export?"):
        st.write("Prijzen krijgen een punt en twee decimalen; voorraad wordt een geheel getal. SKU en productnaam blijven exact gelijk. Bij fouten bevat deze preview lege getalvelden, maar is export geblokkeerd.")
        st.write("Elke SKU krijgt een vaste, unieke Handle op basis van de UTF-8-bytes van de SKU. Extra Shopify-velden: Option1 Name = Title, Option1 Value = Default Title, voorraadtracker = shopify, voorraadbeleid = deny en fulfillment = manual.")
    approved = st.checkbox("Ik heb de kolomkoppeling, alle rijen en de exportregels gecontroleerd.", key=f"approved_{fingerprint}_{tuple(mapping.values())}")
    downloadable = report.empty and approved
    payload = export_shopify(output, report) if downloadable else b""
    st.download_button("Download Shopify CSV", payload, "shopify_products.csv", "text/csv", disabled=not downloadable, key="shopify_download")


if __name__ == "__main__":
    main()
