# Leverancier naar Shopify CSV

Een kleine lokale webapp met Python, pandas en Streamlit. Je uploadt een CSV- of Excel-bestand, bekijkt de eerste tien rijen, koppelt vier kolommen en krijgt een foutenrapport. Als alle rijen goed zijn en je de koppeling bevestigt, kun je de Shopify-CSV downloaden.

De app verandert geen originele bestanden. Bestanden blijven in het geheugen van de lokale app. Er is geen database, account, AI, Shopify-API of externe upload. Streamlit-statistieken zijn uitgeschakeld. Alleen bij het installeren van de dependencies is internet nodig.

## Installeren en starten op Windows

1. Installeer zo nodig Python via https://www.python.org/downloads/windows/. Python 3.12 of 3.13 is een goede keuze. Vink tijdens de installatie **Add Python to PATH** aan. Open daarna een nieuw PowerShell-venster. Controleer met `python --version` of Python werkt.
2. Pak het project uit in een eigen map. Open die map in Verkenner, klik in de adresbalk, typ `powershell` en druk op Enter.
3. Voer deze opdrachten één voor één uit:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

De map `.venv` bevat de packages voor dit project. Je hoeft de omgeving niet te activeren; daarom krijg je ook geen PowerShell-activatieprobleem.

Open in je browser http://127.0.0.1:8501 als dat niet vanzelf gebeurt. Stop de app met **Ctrl+C** in PowerShell. Gebruik bij een volgende start alleen de laatste opdracht. Als `python` niet werkt maar `py` wel, gebruik je `py -m venv .venv` voor de eerste opdracht.

Op macOS/Linux gebruik je `python3 -m venv .venv`, daarna `.venv/bin/python -m pip install -r requirements.txt` en `.venv/bin/python -m streamlit run app.py`.

## Zo gebruik je de app

1. Upload bijvoorbeeld `sample_data/01_correct.csv` of `06_correct.xlsx`.
2. Controleer de kolomnamen en de preview. Bij CSV kun je het scheidingsteken en de tekencodering wijzigen. Bij Excel kies je een werkblad.
3. Controleer de vier dropdowns. Suggesties zijn gebaseerd op kolomnamen, niet op AI. Bij meerdere mogelijke matches moet je zelf kiezen.
4. Bekijk het aantal rijen en de fouten. Download eventueel het foutenrapport. Verbeter bij fouten een **kopie** van het bronbestand en upload die opnieuw.
5. Bij nul fouten: controleer de gegevens en vink de bevestiging aan. Download `shopify_products.csv`.

De preview toont tien rijen; de export bevat alle ingelezen rijen. Een fout in een andere rij blokkeert de export ook. Geen enkele rij wordt automatisch weggegooid. Het foutenrapport bevat alleen rijnummer, type fout en uitleg, zonder de oorspronkelijke celinhoud.

## Vaste regels

| Gegeven | Regel |
| --- | --- |
| SKU | Verplicht, unieke tekst, exact behouden inclusief voorloopnullen. |
| Productnaam | Verplichte tekst, exact behouden. |
| Prijs | Komma of punt als decimaalteken; maximaal twee decimalen; niet negatief. `12,95` wordt `12.95`, `12` wordt `12.00`. Geen afronding. |
| Voorraad | Verplicht, geheel getal vanaf nul. `5`, `5.0` en `5,0` worden `5`. |
| Lege waarden | Fout; nooit automatisch nul of een verzonnen waarde. |
| Duizendtallen/valuta | Niet ondersteund. Gebruik `1234.56`, geen `1.234,56` of `€ 12,95`. `1.000` wordt geblokkeerd wegens mogelijke duizendtalscheiding. |
| Dubbele SKU's | Alle betrokken rijen krijgen een fout. Hoofdletterverschillen en spaties tellen ook als mogelijke dubbele SKU. |
| Spaties in naam/SKU | Aan begin/einde: fout, geen automatische trim. Interne spaties blijven staan. |
| Excel-SKU als getal | Fout. Controleer de echte code en sla de cel opnieuw op als tekst. Een getal `123` kan ooit `000123` zijn geweest; dat is niet te herstellen door te gokken. |
| Formules | Excel-formules worden geweigerd. De app voert ze niet uit. Gebruik vaste waarden in een kopie. |
| Spreadsheet-formuletekens | Naam/SKU met `=`, `+`, `-` of `@` aan het begin wordt geblokkeerd, net als controlekarakters. |

In Excel moet een SKU al als tekst opgeslagen zijn. Alleen de weergave aanpassen naar bijvoorbeeld `000000` is onvoldoende: onderliggend kan het nog steeds een getal zijn. Tekst-SKU's `NA`, `NULL` en `nan` blijven gewone tekst.

De kopregel is rij 1 en de eerste datarij is rij 2. Bij CSV met regeleinden binnen quotes telt het foutenrapport CSV-records, geen fysieke tekstregels. Lege CSV-regels blijven datarijen en krijgen fouten. Bij Excel wordt het opgegeven werkbladbereik niet vertrouwd: de app leest de werkelijk opgeslagen rijen, zodat verkeerde bereikgegevens geen producten verbergen. Expliciet opgeslagen lege of opgemaakte rijen kunnen fouten opleveren. Kies in dat geval een opgeschoonde kopie. Excel-foutcellen zoals `#N/A` worden geweigerd.

## Shopify-export en grenzen

De CSV gebruikt komma's tussen kolommen, punten in prijzen en UTF-8 met BOM. De vier gevraagde velden zijn `Title`, `Variant SKU`, `Variant Price` en `Variant Inventory Qty`.

Aanvullende vaste Shopify-velden:

| Veld | Waarde |
| --- | --- |
| Handle | `supplier-` gevolgd door de UTF-8-bytes van de SKU als hextekst. Dit geeft een vaste, unieke producthandle zonder SKU's te veranderen. |
| Option1 Name | `Title` |
| Option1 Value | `Default Title` |
| Variant Inventory Tracker | `shopify` |
| Variant Inventory Policy | `deny` |
| Variant Fulfillment Service | `manual` |

Deze versie behandelt **iedere rij als een nieuw, los product met één standaardvariant**. Producten met dezelfde naam blijven losse producten dankzij de Handle. Er is geen koppeling met bestaande producthandles. Gebruik dit bestand daarom niet om bestaande producten/varianten bij te werken. Er is geen import in een echte winkel uitgevoerd.

Shopify ondersteunt de oudere kolomnamen die hier op verzoek zijn gebruikt. De officiële documentatie vermeldt dat variantvelden ook optiekolommen nodig hebben en dat voorraad in een product-CSV bedoeld is voor een winkel met één voorraadlocatie. Bron: https://help.shopify.com/en/manual/products/import-export/using-csv

Beperkingen: maximaal 10 MB, 50.000 datarijen en 100 kolommen; maximaal 50 MB uitgepakte Excel-inhoud. Alleen `.csv` en `.xlsx`, geen `.xls`. Eén werkblad tegelijk. Geen afbeeldingen, productgroepen, verschillende valuta of belastingberekeningen. CSV met beschadigde quotes, ongelijke aantallen velden of dubbele kolomnamen wordt volledig geweigerd in plaats van gedeeltelijk verwerkt.

Wanneer je een CSV in Excel opent, kan **Excel zelf** voorloopnullen verwijderen of prijzen anders weergeven. Importeer via **Gegevens → Van tekst/CSV** en stel de SKU-kolom in als tekst. Bewaar de originele download; de tests lezen CSV's als tekst om dit te controleren.

## Bestanden en belangrijkste code

| Bestand | Doel |
| --- | --- |
| `app.py` | De Streamlit-pagina: upload, preview, dropdowns, controles, bevestiging en downloads. |
| `converter.py` | Lezen, kolomsuggesties, getalregels, rijcontroles en export. Apart gehouden zodat de regels zonder webapp getest kunnen worden. |
| `requirements.txt` | De drie benodigde packages. |
| `.streamlit/config.toml` | Alleen lokale toegang, uploadlimiet en statistieken uit. |
| `tests/test_converter.py` | Tests voor conversie en bestandsbehoud. |
| `tests/test_app.py` | Streamlit-interfacechecks met een upload in geheugen. |
| `sample_data/` | Zes volledig fictieve leveranciersbestanden. |
| `EINDRAPPORT.md` | Uitgevoerde tests, oplossingen en beperkingen van de controle. |

`read_supplier_file()` leest alleen bytes in geheugen. Voor CSV gebruiken we Python's CSV-lezer zodat tekstcodes en lege rijen behouden blijven. Voor Excel gebruiken we openpyxl, zodat we formules en numerieke SKU's herkennen. Beide leveren een pandas-DataFrame op.

`suggest_mapping()` vergelijkt kolomnamen met korte lijsten zoals `productnaam`, `sku`, `prijs` en `voorraad`. `convert_products()` leest iedere rij volgens de gekozen koppeling. `parse_number()` gebruikt `Decimal`, zodat prijsregels geen binaire afrondfouten introduceren. `export_shopify()` weigert uitvoer bij fouten. `csv_bytes()` maakt de downloadbare CSV.

## Tests uitvoeren

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Geen apart testpakket nodig: `unittest` hoort bij Python. Interfacechecks gebruiken Streamlit's eigen `AppTest`; als Streamlit ontbreekt worden die expliciet overgeslagen. Een resultaat met `skipped` betekent dus niet dat alle appchecks uitgevoerd zijn.

Bij de laatste controle zijn 26 conversietests daadwerkelijk uitgevoerd en geslaagd. Vier interfacechecks zijn niet uitgevoerd doordat Streamlit niet geïnstalleerd was en installatie in de testomgeving niet lukte. De startopdracht is opnieuw geprobeerd, maar gaf `No module named streamlit`. Een echte browserflow van upload tot download is daardoor nog niet gecontroleerd. Zie het eindrapport voor de precieze status.

Voer na installatie ook deze browsercontrole uit:

1. Start de app en upload `01_correct.csv`. Er moeten 3 rijen en 0 fouten zijn.
2. Verander een kolomkoppeling en controleer dat het resultaat opnieuw wordt berekend. Zet de koppeling terug.
3. Vink de bevestiging aan, download de Shopify-CSV en open die als tekst. Controleer `000123` en `12.95`, plus alle 3 rijen.
4. Upload `06_correct.xlsx` en herhaal de download.
5. Upload `04_sku_fouten.csv`. Verwacht 3 fouten; de Shopify-download blijft uitgeschakeld, ook met bevestiging. Download en open het foutenrapport.
6. Upload `05_meerdere_fouten.csv`. Verwacht 8 rijen en 10 fouten; geen productexport.

## Later uitbreiden

Begin bij één kleine toevoeging tegelijk. Voor een extra veld voeg je de naam en kolomherkenning toe in `converter.py`, schrijf je de controle en pas je de pagina en tests aan. Voeg eerst fictieve testdata toe voor geldig én foutief gebruik.

Drie logische vervolgstappen:

1. Kolomkoppelingen lokaal opslaan en opnieuw laden per leverancier.
2. Fouten in de app corrigeren met een zichtbare vergelijking tussen bron en wijziging.
3. Productvarianten en meerdere voorraadlocaties ondersteunen met aparte, duidelijke exportregels.
