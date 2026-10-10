# Eindrapport — 7 oktober 2026

## Hertest en bugfixes

Op verzoek is de software opnieuw getest en zijn zes extra regressietests toegevoegd. Resultaat: **26 tests geslaagd, 4 Streamlit-interfacechecks overgeslagen**. Syntaxcontrole is ook geslaagd.

Gevonden en gecorrigeerd:

1. **Excel-rijen konden ongemerkt verdwijnen.** Met een foutief werkbladbereik `A1:A1` gaf de oude lezer nul producten terug, terwijl de gegevens wel in het bestand stonden. Ontbrekende bereikgegevens veroorzaakten een TypeError. De app leest nu de werkelijke rijen en controleert limieten tijdens het lezen. Getest met te klein, ontbrekend en veel te groot opgegeven bereik.
2. **Excel-foutcellen konden als SKU worden geaccepteerd.** Foutcellen zoals `#N/A` worden nu expliciet geblokkeerd met de celpositie, zodat ze geen productcodes worden.
3. **Negatieve nul werd als `-0.00` geëxporteerd.** Dit wordt nu `0.00`, zonder de numerieke waarde te veranderen.

Extra tests controleren ontbrekende cellen aan het einde van een Excel-rij, gegevens buiten de kopkolommen en de rij-/kolomlimieten van CSV en Excel. Alle bestaande conversietests blijven slagen, inclusief rijbehoud, originele bestanden ongewijzigd, export opnieuw openen en foutieve export blokkeren.

De gebruikte aanpak voor onbetrouwbare werkbladbereiken is ook beschreven in de openpyxl-documentatie: https://openpyxl.readthedocs.io/en/stable/optimized.html#worksheet-dimensions

**Nog niet geverifieerd:** Streamlit kon opnieuw niet worden geïnstalleerd (`No matching distribution found` in deze omgeving). De startpoging gaf opnieuw `No module named streamlit`. De vier interfacechecks en de echte browserflow zijn daarom niet uitgevoerd. De software is dus niet volledig end-to-end goedgekeurd.

## Gebouwd

Een klein lokaal Python-project met Streamlit-interface en pandas voor verwerking. Upload van CSV/XLSX, preview van tien rijen, handmatige kolomkoppeling met wijzigbare suggesties, vaste controles, Shopify-CSV en apart foutenrapport. Alle rijen blijven aanwezig; bij fouten is de Shopify-download geblokkeerd. Voor download moet de gebruiker de koppeling en gegevens bevestigen.

Zes fictieve bestanden: correct CSV, Nederlandse kolomnamen, kommaprijzen, dubbele/ontbrekende SKU's, meerdere fouten en correct Excel. Originele bronbestanden worden uitsluitend gelezen. Geen externe uploads, winkelverbinding, API, database of geheime gegevens.

## Uitgevoerde controles

Omgeving: Windows, Python 3.12.14, pandas 3.0.1 en openpyxl 3.1.5. Conversietests draaien met Python's standaard `unittest`.

| Controle | Status |
| --- | --- |
| CSV lezen; komma/puntkomma; quotes; Windows-1252 | Geslaagd |
| Excel lezen; expliciet werkblad kiezen; tekst-SKU behouden | Geslaagd |
| Nederlandse kolommen; handmatige koppeling; ongeldige koppeling | Geslaagd |
| Komma/punt/Excel-prijzen; nul; vaste tweedecimale export | Geslaagd |
| Ontbrekende SKU/naam/prijs/voorraad; alle dubbele SKU-rijen | Geslaagd |
| Negatieve/onleesbare prijzen; ongeldige/negatieve/breukvoorraad | Geslaagd |
| Geen gokken of afronden; geen numerieke Excel-SKU's/formules | Geslaagd |
| Beschadigde CSV; ongeldige extensie; beschadigde XLSX; uploadlimiet | Geslaagd |
| Shopify-CSV en foutenrapport schrijven en opnieuw openen | Geslaagd |
| Alle zes testbestanden: rijbehoud en bronhash onveranderd | Geslaagd |
| Voorloopnullen en prijzen in export opnieuw gecontroleerd | Geslaagd |
| Python-syntaxcontrole | Geslaagd |
| Vier Streamlit-interfacechecks | Overgeslagen: Streamlit ontbreekt |
| Streamlit-server daadwerkelijk starten | Geprobeerd, mislukt: `No module named streamlit` |
| Echte browserflow upload → download | Niet uitgevoerd door ontbrekende Streamlit-installatie |
| Import in echte Shopify-winkel | Niet uitgevoerd; valt buiten deze MVP |

De lokale bestandsflow is daadwerkelijk uitgevoerd: bronbytes lezen → koppeling → controles → exportbytes → nieuw tijdelijk CSV-bestand → opnieuw lezen → waarden en rijaantal vergelijken. Voor foutieve bronnen is de productexport terecht geweigerd en is het foutenrapport opnieuw geopend. Dit is geen browser-uploadtest.

## Gevonden en opgelost

- De eerste exporttests faalden doordat pandas 3 opnieuw ingelezen tekst als een ander intern teksttype opslaat. De tests vergelijken nu alle waarden, rijen en kolommen zonder dat interne opslagtype. SKU's en bedragen waren gelijk; er was geen dataverlies.
- Bij controle van de getalregels bleek dat `1.000` als voorraad 1 kon worden gelezen, terwijl een leverancier mogelijk 1000 bedoelt. Getallen met meer dan twee decimalen worden nu geweigerd; de app interpreteert geen duizendtalscheiding. Ook prijzen met extra decimalen worden geblokkeerd in plaats van afgerond.
- De dependency-installatie werd geblokkeerd door netwerktoegang in de uitvoeromgeving. De conversietests zijn omgezet naar ingebouwde `unittest`, zodat ze daadwerkelijk uitgevoerd konden worden. Streamlit zelf is daardoor nog niet uitgevoerd; dit probleem is niet opgelost binnen deze omgeving.

## Beperkingen en volgende stappen

De conversielogica is getest; de werking van de Streamlit-pagina in een echte browser is nog niet bewezen. Installeer de requirements en voer de interfacechecks en de browsercontrole uit zoals beschreven in README.md.

De MVP behandelt één rij als een los product met standaardvariant, voor één Shopify-voorraadlocatie. Geen ondersteuning voor bestaande-productupdates, variantgroepering, afbeeldingen, valutaomrekening of duizenden-scheiding. Numerieke Excel-SKU's moeten gecontroleerd als tekst worden aangeleverd. Een echte Shopify-import is niet gevalideerd.

De drie logische vervolgstappen zijn: lokale opgeslagen kolomkoppelingen, zichtbare correcties binnen de app en ondersteuning voor productvarianten/meerdere voorraadlocaties.
