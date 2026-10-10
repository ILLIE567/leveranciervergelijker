import hashlib
import json
import os
import tempfile
from pathlib import Path

import pandas as pd

from converter import (
    FIELDS,
    convert_products,
    csv_bytes,
    excel_sheet_names,
    read_supplier_file,
    suggest_mapping,
)

PROFILE_FILE = Path(__file__).resolve().with_name("leveranciers.json")

REPORT_COLUMNS = [
    "SKU", "Productnaam", "Wijziging", "Oude waarde", "Nieuwe waarde"
]


def load_profiles():
    """Lees de opgeslagen kolomkoppelingen."""
    try:
        text = PROFILE_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}

    try:
        profiles = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(
            "leveranciers.json bevat geen geldige instellingen."
        ) from error

    if not isinstance(profiles, dict):
        raise ValueError("leveranciers.json heeft een ongeldige inhoud.")

    for name, mapping in profiles.items():
        if (
            not isinstance(name, str)
            or not name.strip()
            or not isinstance(mapping, dict)
        ):
            raise ValueError("Er staat een ongeldig leveranciersprofiel.")

        for field in FIELDS:
            column = mapping.get(field)
            if not isinstance(column, str) or not column.strip():
                raise ValueError(
                    f"De instellingen van '{name}' zijn onvolledig."
                )

        columns = [mapping[field] for field in FIELDS]
        if len(set(columns)) != len(columns):
            raise ValueError(
                f"De instellingen van '{name}' bevatten dubbele koppelingen."
            )

    return profiles


def save_profile(name, mapping):
    """Bewaar een leverancier zonder andere profielen te verwijderen."""
    profiles = load_profiles()
    profiles[name] = {field: mapping[field] for field in FIELDS}

    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=PROFILE_FILE.parent,
            prefix="leveranciers_",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            json.dump(
                profiles,
                temporary,
                ensure_ascii=False,
                indent=2,
            )
            temporary.write("\n")

        os.replace(temporary_path, PROFILE_FILE)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def compare_products(old_products, new_products):
    """Controleer beide bestanden en vergelijk op exact dezelfde SKU."""
    tables = []

    for label, products in (
        ("oude", old_products),
        ("nieuwe", new_products),
    ):
        clean, errors = convert_products(
            products, {field: field for field in FIELDS}
        )

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
            before = previous[field]
            after = product[field]

            if before != after:
                if (
                    field == "Variant Inventory Qty"
                    and int(before) > 0
                    and int(after) == 0
                ):
                    change_type = "Voorraad gewijzigd (uitverkocht)"

                changes.append([sku, name, change_type, before, after])

    for sku, product in old.iterrows():
        if sku not in new.index:
            changes.append([
                sku,
                product["Title"],
                "Ontbreekt in nieuw bestand",
                product["Title"],
                "",
            ])

    return pd.DataFrame(changes, columns=REPORT_COLUMNS, dtype=object)


def upload_products(label, key, profiles, saving_allowed):
    import streamlit as st

    st.subheader(label)

    uploaded = st.file_uploader(
        "Kies een CSV- of Excel-bestand",
        type=["csv", "xlsx"],
        key=f"upload_{key}",
    )

    if uploaded is None:
        return None

    data = uploaded.getvalue()
    delimiter = None
    encoding = "utf-8-sig"
    sheet = None

    try:
        if uploaded.name.lower().endswith(".csv"):
            separators = {
                "Automatisch": None,
                "Puntkomma": ";",
                "Komma": ",",
                "Tab": "\t",
            }

            choice = st.selectbox(
                "Scheidingsteken",
                list(separators),
                key=f"separator_{key}",
            )
            delimiter = separators[choice]

            code = st.selectbox(
                "Tekencodering",
                ["UTF-8", "Windows-1252"],
                key=f"encoding_{key}",
            )
            encoding = "utf-8-sig" if code == "UTF-8" else "cp1252"
        else:
            sheet = st.selectbox(
                "Werkblad",
                excel_sheet_names(data),
                key=f"sheet_{key}",
            )

        frame = read_supplier_file(
            data,
            uploaded.name,
            delimiter=delimiter,
            encoding=encoding,
            sheet_name=sheet,
        )
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
        format_func=lambda value: (
            "Zelf instellen" if value is None else value
        ),
        key=f"supplier_{key}",
    )

    saved_mapping = profiles[supplier] if supplier is not None else {}
    suggestions = suggest_mapping(frame.columns)
    options = [None] + list(frame.columns)

    if supplier is not None:
        missing = [
            saved_mapping[field]
            for field in FIELDS
            if saved_mapping[field] not in frame.columns
        ]

        if missing:
            st.warning(
                "Deze opgeslagen kolommen ontbreken: "
                + ", ".join(missing)
                + ". Kies daarvoor hieronder de juiste kolommen."
            )
        else:
            st.caption(
                f"De kolomkoppelingen van '{supplier}' zijn ingevuld."
            )

    fingerprint = hashlib.sha256(
        data + str((delimiter, encoding, sheet)).encode()
    ).hexdigest()[:16]

    profile_token = hashlib.sha256(
        json.dumps(
            [supplier, saved_mapping],
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:16]

    mapping = {}
    st.write("Controleer de kolomkoppelingen:")

    for field in FIELDS:
        if supplier is not None:
            default = saved_mapping[field]
        else:
            default = suggestions.get(field)

        if default not in options:
            default = None

        mapping[field] = st.selectbox(
            field,
            options,
            index=options.index(default),
            format_func=lambda value: (
                "Kies een kolom" if value is None else value
            ),
            key=f"mapping_{key}_{fingerprint}_{profile_token}_{field}",
        )

    complete = all(value is not None for value in mapping.values())
    unique = complete and len(set(mapping.values())) == len(FIELDS)

    name_token = hashlib.sha256(
        (supplier or "").encode("utf-8")
    ).hexdigest()[:16]

    with st.expander("Bewaar deze kolomkoppelingen"):
        profile_name = st.text_input(
            "Naam van leverancier",
            value=supplier or "",
            placeholder="Bijvoorbeeld: Leverancier A",
            key=f"profile_name_{key}_{name_token}",
        ).strip()

        overwrite_allowed = True

        if profile_name and profile_name in profiles:
            overwrite_allowed = st.checkbox(
                f"Vervang de opgeslagen instellingen van '{profile_name}'",
                key=f"overwrite_{key}_{profile_name}",
            )

        st.caption(
            "Alleen de kolomkoppelingen worden bewaard. "
            "Je kunt deze leverancier daarna bij beide bestanden kiezen."
        )

        can_save = (
            saving_allowed
            and complete
            and unique
            and bool(profile_name)
            and overwrite_allowed
        )

        if not saving_allowed:
            st.warning(
                "Bewaren is niet beschikbaar omdat de opgeslagen "
                "instellingen niet konden worden gelezen."
            )

        if st.button(
            "Instellingen bewaren",
            key=f"save_profile_{key}",
            disabled=not can_save,
        ):
            try:
                save_profile(profile_name, mapping)
            except (OSError, ValueError) as error:
                st.error(f"Bewaren is niet gelukt: {error}")
            else:
                st.session_state["profile_notice"] = (
                    f"Instellingen van '{profile_name}' bewaard. "
                    "Je kunt deze leverancier nu in de keuzelijst kiezen."
                )
                st.rerun()

    if not complete:
        st.warning("Koppel eerst alle vier velden.")
        return None

    if not unique:
        st.error("Kies voor ieder veld een verschillende kolom.")
        return None

    try:
        products, errors = convert_products(frame, mapping)
    except ValueError as error:
        st.error(str(error))
        return None

    if not errors.empty:
        st.error(
            f"{len(errors)} fouten. Los deze op voordat je vergelijkt."
        )
        st.dataframe(errors, hide_index=True)
        st.download_button(
            "Download foutenrapport",
            csv_bytes(errors),
            f"foutenrapport_{key}.csv",
            "text/csv",
            key=f"errors_{key}",
        )
        return None

    st.success("Bestand goedgekeurd.")
    return products


def main():
    import streamlit as st

    st.set_page_config(
        page_title="Leveranciersbestanden vergelijken",
        layout="wide",
    )

    st.title("Wat is er veranderd?")
    st.write(
        "Upload een oud en een nieuw leveranciersbestand. "
        "De app vergelijkt productnaam, prijs en voorraad op SKU."
    )
    st.info(
        "Ontbrekende producten worden alleen gemeld. "
        "Er worden geen producten verwijderd of bestanden gewijzigd. "
        "Een gewijzigde SKU telt als een ontbrekend en een nieuw product."
    )

    notice = st.session_state.pop("profile_notice", None)
    if notice:
        st.success(notice)

    saving_allowed = True

    try:
        profiles = load_profiles()
    except (OSError, ValueError) as error:
        profiles = {}
        saving_allowed = False
        st.error(f"Leveranciersinstellingen konden niet worden gelezen: {error}")

    left, right = st.columns(2)

    with left:
        old = upload_products(
            "1. Oud bestand", "old", profiles, saving_allowed
        )

    with right:
        new = upload_products(
            "2. Nieuw bestand", "new", profiles, saving_allowed
        )

    if old is None or new is None:
        st.write("Upload twee foutvrije bestanden om te vergelijken.")
        return

    try:
        report = compare_products(old, new)
    except ValueError as error:
        st.error(str(error))
        return

    st.subheader("3. Veranderingen")
    st.write(f"Oud: {len(old)} producten. Nieuw: {len(new)} producten.")

    if report.empty:
        st.success("Geen veranderingen gevonden.")
    else:
        st.write(
            f"{len(report)} veranderingen gevonden. "
            "Eén product kan meerdere wijzigingen hebben."
        )
        st.dataframe(report, hide_index=True)

    st.caption(
        "SKU's worden exact vergeleken, inclusief hoofdletters "
        "en voorloopnullen. 12,95 en 12.95 tellen als hetzelfde bedrag."
    )
    st.download_button(
        "Download veranderingenrapport",
        csv_bytes(report),
        "veranderingenrapport.csv",
        "text/csv",
    )


if __name__ == "__main__":
    main()