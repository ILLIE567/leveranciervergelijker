"""Translate app-owned report text; preserve supplier data and identifiers."""

import re

ERROR_TEXT = {
    "Elke kolom moet een niet-lege tekstnaam hebben op de eerste rij.": "Every column must have a non-empty text header in the first row.",
    "Dubbele kolomnamen gevonden. Maak de namen eerst uniek.": "Duplicate column names found. Give each column a unique name first.",
    "Maximaal 100 kolommen toegestaan.": "A maximum of 100 columns is allowed.",
    "Het bestand is leeg.": "The file is empty.",
    "Het bestand is te groot. Maximaal 10 MB toegestaan.": "The file is too large. The maximum size is 10 MB.",
    "Tekencodering niet leesbaar. Kies UTF-8 of Windows-1252.": "The text encoding could not be read. Choose UTF-8 or Windows-1252.",
    "Dit bestand lijkt geen tekst-CSV te zijn.": "This file does not appear to be a text CSV file.",
    "Scheidingsteken niet herkend. Kies het handmatig.": "The separator could not be detected. Select it manually.",
    "Kies komma, puntkomma of tab als scheidingsteken.": "Choose a comma, semicolon or tab as the separator.",
    "Maximaal 50000 datarijen toegestaan; er wordt niets afgekapt.": "A maximum of 50,000 data rows is allowed; no rows will be silently removed.",
    "Ongeldige of lege CSV. Controleer de aanhalingstekens en kopregel.": "Invalid or empty CSV. Check the quotation marks and header row.",
    "Excel-bestand is uitgepakt te groot (maximaal 50 MB).": "The uncompressed Excel file is too large (maximum 50 MB).",
    "Dit bestand is geen leesbaar .xlsx-bestand.": "This file is not a readable .xlsx file.",
    "Meerdere werkbladen gevonden. Kies eerst een werkblad.": "Multiple worksheets found. Select a worksheet first.",
    "Het gekozen werkblad bestaat niet.": "The selected worksheet does not exist.",
    "Alleen .csv en .xlsx worden ondersteund.": "Only .csv and .xlsx files are supported.",
    "Koppel alle vier Shopify-velden aan bestaande leverancierskolommen.": "Map all four fields to existing supplier columns.",
    "Gebruik voor elk Shopify-veld een andere leverancierskolom.": "Use a different supplier column for each field.",
    "Dubbele SKU": "Duplicate SKU",
    "SKU komt meerdere keren voor (ook hoofdletterverschillen/spaties tellen mee). Controleer alle betrokken rijen.": "This SKU occurs more than once (including differences in case or surrounding spaces). Check all affected rows.",
    "Prijs heeft meer dan twee decimalen; de app rondt niet automatisch af.": "The price has more than two decimal places; the app does not round automatically.",
    "Voorraad heeft meer dan twee decimalen of een mogelijke duizendtalscheiding. Gebruik een geheel getal zonder scheiding.": "Stock has more than two decimal places or a possible thousands separator. Use a whole number without separators.",
    "Voorraad moet een geheel getal zijn.": "Stock must be a whole number.",
    "Gebruik een instellingenbestand met maximaal 100 leveranciers.": "Use a settings file with no more than 100 suppliers.",
    "Een leveranciersnaam moet 1 tot 80 tekens bevatten.": "A supplier name must contain 1 to 80 characters.",
    "Elke leverancier moet vier kolomkoppelingen bevatten.": "Each supplier must have four column mappings.",
    "Koppel voor iedere leverancier alle vier velden.": "Map all four fields for each supplier.",
    "Kies voor ieder veld een verschillende kolom.": "Choose a different column for each field.",
    "Bevestig eerst dat je deze leverancier wilt vervangen.": "Confirm that you want to replace this supplier first.",
    "Het instellingenbestand is te groot (maximaal 256 KB).": "The settings file is too large (maximum 256 KB).",
    "Dit is geen geldig instellingenbestand in UTF-8.": "This is not a valid UTF-8 settings file.",
}

for dutch, english in (("Prijs", "Price"), ("Voorraad", "Stock")):
    ERROR_TEXT.update({
        f"Ongeldige {dutch.lower()}": f"Invalid {english.lower()}",
        f"{dutch} ontbreekt.": f"{english} is missing.",
        f"{dutch} moet een getal zijn, geen ja/nee-waarde.": f"{english} must be a number, not a yes/no value.",
        f"{dutch} is geen geldig getal. Gebruik bijvoorbeeld 12,95 of 12.95, zonder valuta of duizendtalscheiding.": f"{english} is not a valid number. Use a value such as 12,95 or 12.95, without a currency symbol or thousands separator.",
        f"{dutch} mag niet negatief zijn.": f"{english} cannot be negative.",
        f"{dutch} valt buiten het ondersteunde getalbereik.": f"{english} is outside the supported numeric range.",
    })

for dutch, english in (("Productnaam", "Product name"), ("SKU", "SKU")):
    for prefix_nl, prefix_en in (("Ontbrekende", "Missing"), ("Ongeldige", "Invalid"), ("Spaties bij", "Spaces around"), ("Controlekarakter in", "Control character in"), ("Onveilige", "Unsafe")):
        ERROR_TEXT[f"{prefix_nl} {dutch.lower()}"] = f"{prefix_en} {english.lower()}"
    ERROR_TEXT.update({
        f"{dutch} ontbreekt.": f"{english} is missing.",
        f"{dutch} is geen tekst. Sla deze Excel-cel op als tekst. Voorloopnullen kunnen al verloren zijn gegaan; de app verzint ze niet.": f"{english} is not text. Save this Excel cell as text. Leading zeros may already have been lost; the app does not invent them.",
        f"{dutch} heeft spaties aan het begin of einde. Pas dit aan in een kopie van het bronbestand.": f"{english} has leading or trailing spaces. Correct this in a copy of the source file.",
        f"{dutch} bevat een tab, regeleinde of ander controlekarakter.": f"{english} contains a tab, line break or other control character.",
        f"{dutch} begint met een spreadsheet-formuleteken. Controleer dit handmatig; de app wijzigt de tekst niet.": f"{english} starts with a spreadsheet formula character. Check this manually; the app does not change the text.",
    })

for dutch, english in (("oude", "old"), ("nieuwe", "new")):
    ERROR_TEXT[f"Het {dutch} bestand bevat fouten."] = f"The {english} file contains errors."
    ERROR_TEXT[f"Het {dutch} bestand bevat geen producten."] = f"The {english} file contains no products."

DYNAMIC_ERRORS = (
    (r"Een CSV-veld bevat te veel tekst \(maximaal (\d+) tekens\)\.", "A CSV field contains too much text (maximum {0} characters)."),
    (r"CSV-record (\d+): (\d+) velden, verwacht (\d+)\. Controleer scheidingstekens en quotes\.", "CSV record {0}: {1} fields, expected {2}. Check the separators and quotation marks."),
    (r"Excel-rij (\d+) bevat cellen buiten de kolomnamen\. Geef elke kolom een naam\.", "Excel row {0} contains cells beyond the column headers. Give every column a name."),
    (r"Excel-formule op (.+)\. Vervang formules door vaste waarden in een kopie\.", "Excel formula in {0}. Replace formulas with fixed values in a copy."),
    (r"Excel-foutwaarde op (.+)\. Corrigeer deze cel in een kopie\.", "Excel error value in {0}. Correct this cell in a copy."),
)

CHANGE_TEXT = {
    "Nieuw product": "New product",
    "Naam gewijzigd": "Name changed",
    "Prijs gewijzigd": "Price changed",
    "Voorraad gewijzigd": "Stock changed",
    "Voorraad gewijzigd (uitverkocht)": "Stock changed (out of stock)",
    "Ontbreekt in nieuw bestand": "Missing from new file",
}


def translate_error(message, language="en"):
    if language == "nl":
        return message
    if message in ERROR_TEXT:
        return ERROR_TEXT[message]
    for pattern, template in DYNAMIC_ERRORS:
        match = re.fullmatch(pattern, message)
        if match:
            return template.format(*match.groups())
    return message


def localize_report(report, language="en"):
    result = report.copy(deep=True)
    if language == "en":
        result["Wijziging"] = result["Wijziging"].replace(CHANGE_TEXT)
        result = result.rename(columns={"Productnaam": "Product name", "Wijziging": "Change", "Oude waarde": "Old value", "Nieuwe waarde": "New value"})
    return result


def localize_errors(errors, language="en"):
    result = errors.copy(deep=True)
    if language == "en":
        for column in ("Type fout", "Uitleg"):
            result[column] = result[column].map(translate_error)
        result = result.rename(columns={"Rijnummer": "Row", "Type fout": "Error type", "Uitleg": "Explanation"})
    return result
