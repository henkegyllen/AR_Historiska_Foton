# AR Historiska Foton – Sommargatan Växjö

Web-AR som lägger ett **historiskt foto** över **nuläget**, så att besökaren kan
jämföra då och nu på plats. Byggd på samma teknik som Kalasvärlden/Sommargatan
(A-Frame, ingen app, ingen markördetektion) men visar fotoplan istället för 3D-modeller.

**🔗 Live:** https://henkegyllen.github.io/AR_Historiska_Foton/

QR-kod till sidan: [`qr_historiska_foton.png`](qr_historiska_foton.png)

## Så funkar det

1. Besökaren skannar en **QR-kod** och öppnar sidan.
2. Hen ställer sig med fötterna på **två målade fotsteg** på marken. Fotstegen
   ligger på fotografens gamla plats och pekar i fotoriktningen.
3. "Starta" låser riktningen ur fotstegsbäringen + telefonens gyro:
   `rotY = fotstegsbäring + gyro-yaw + HEADING_OFFSET`
4. Det historiska fotot visas halvtransparent framför besökaren.
   **Toningsreglaget** fadar mot nuläget; **vrid-knapparna ◀ ▶** finjusterar inpassningen.

- **Android (Chrome/ARCore):** positionsspårning → gå fram och runt.
- **iPhone (Safari):** ingen positionsspårning → stå på fotstegen och vrid dig.

## Data — `assets/foton.csv`

En rad per foto (en 2-punktslinje ur linjelagret):

```
namn,lat1,lon1,lat2,lon2,elev,distans,bredd,hojd,rot
Exempel.jpg,56.877892,14.805083,56.877899,14.806207,,12,14,2.0,0
```

| Fält | Betydelse |
|------|-----------|
| `namn` | Bildfil i `assets/foton/` |
| `lat1,lon1` | Fotografens plats = där fotstegen målas (origo + ståpunkt) |
| `lat2,lon2` | Riktpunkt → bäring = riktning p1→p2 |
| `elev` | Markhöjd vid fotstegen (m), valfri |
| `distans` | Hur långt fram (m) fotoplanet skjuts. Default 12 |
| `bredd` | Fotoplanets bredd (m); höjd räknas ur bildens format. Default 16 |
| `hojd` | Planets centrumhöjd (m). Default 1.6 |
| `rot` | Extra grader (fältjustering). Default 0 |

Första raden definierar origo + fotstegsbäring för hela vyn.

## Synk från linjelagret

Linjerna underhålls i ett ArcGIS-linjelager (fält `foto_referens` = bild-URL).
`tools/sync_from_featureserver.py` hämtar lagret via en inloggad ArcGIS
Pro-session, laddar ner + skalar bilderna ur `foto_referens`, och skriver om
`foton.csv`. Manuella trim-värden bevaras per bildnamn.

Serveradressen ligger **inte** i repot. Kopiera `tools/sync.config.example.json`
till `tools/sync.config.json` (gitignorerad) och fyll i din egen FeatureServer-URL,
eller sätt miljövariabeln `AR_FEATURESERVER_URL`. Kör sedan skriptet med
ArcGIS Pro:s medföljande Python (propy) medan du är inloggad mot din portal.

Filnamn tas från fältet **`bildfil`** i tjänsten om det finns (rekommenderas –
då styr ni namnet), annars media-id ur `foto_referens`.

Linjelagret lagras i **SWEREF 99 15 00** (EPSG:3007). Sync-skriptet begär
`outSR=4326` så att servern omprojicerar till **WGS84** – `foton.csv` och appens
matematik arbetar i WGS84 (lat/lon).

## Fältjustering

- `HEADING_OFFSET` i `index.html` — global rättning av snedvridning (fältmäts, +medurs).
- Vrid-knapparna ◀ ▶ — besökarens egen finjustering under visning.
- `distans` / `bredd` / `hojd` / `rot` per foto — matcha fotot mot verkligheten.

## Versionshantering

Vid varje skarp ändring: höj **både** `APP_VERSION` i `index.html` och `version`
i `version.json` (tvingar iOS Safari att hämta ny sida).

## Bilder

Historiska foton läggs i `assets/foton/` (inte länkas externt – WebGL kräver
samma-origin för texturer, annars blockeras de av CORS). Skala ner till ~1600 px.
Rättigheter måste vara klarerade före publicering.
