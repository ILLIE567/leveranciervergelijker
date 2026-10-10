# Leveranciersbestanden vergelijken — openbare testversie

Een Streamlit-demo voor het vergelijken van twee leveranciersbestanden. De pagina
start met fictieve oefenbestanden: twintig producten per bestand en vijf bekende
veranderingen. Bezoekers kunnen daarna hun eigen CSV- of XLSX-bestanden proberen.

De interface start in het Engels. Kies **Language / Taal** in de zijbalk om naar
Nederlands te wisselen. Rapporten en foutmeldingen volgen de gekozen taal;
productgegevens, SKU's en bronkolomnamen blijven ongewijzigd.

## Online zetten

1. Maak op GitHub een repository en upload de inhoud van deze map. Upload geen
   persoonlijke leveranciersbestanden, lokale `.venv` of `leveranciers.json`.
2. Open https://share.streamlit.io/ en meld je aan met GitHub.
3. Kies **Create app**, vervolgens **Yup, I have an app**.
4. Selecteer de repository en branch. Het startbestand is **streamlit_app.py**.
5. Kies in **Advanced settings** Python **3.12** of **3.13** en klik **Deploy**.
6. Controleer in de deelinstellingen dat de app publiek toegankelijk is.
7. Open de internetlink in een privévenster. Controleer of de demo vijf wijzigingen
   toont. Deel daarna deze link met testers.

Documentatie:
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
- https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app

## Lokaal starten

```powershell
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

## Instellingen en uploads

Elke bezoekerssessie heeft eigen uploads en eigen leveranciersinstellingen. De
app schrijft uploads en leveranciersprofielen niet naar gedeelde bestanden en
gebruikt hiervoor geen globale cache. Instellingen blijven tijdens het bezoek
beschikbaar. Download ze als JSON voor een volgend bezoek en laad dat bestand
later weer in. Een bestaande lokale `leveranciers.json` kan ook worden ingelezen.

Uploads worden op de hostingserver in het geheugen verwerkt. Gebruik voor de
publieke test fictieve of geanonimiseerde productgegevens. Maximaal 10 MB per
bestand, 50.000 rijen en 100 kolommen. De app voert Excel-formules niet uit.

## Grenzen

- De vergelijking gebruikt de exacte SKU. EAN-koppelingen ontbreken nog.
- Ontbrekende producten worden uitsluitend gemeld; er wordt geen voorraad aangepast.
- De gebruiker kiest zelf de juiste prijskolom en btw-basis.
- Extra kolommen blijven buiten de vergelijking.
- De download is een veranderingenrapport, geen importbestand voor bestaande
  Shopify-producten. Er is geen Shopify-koppeling.
- De feedbackknop verwijst naar het bestaande Shopify-forumtopic. De app zelf
  verzamelt geen feedback of contactgegevens.

## Tests

```powershell
python -m unittest discover -s tests -v
```

De originele lokale app blijft buiten dit pakket en wordt niet gewijzigd.
