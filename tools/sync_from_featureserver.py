# -*- coding: utf-8 -*-
"""
Synkar AR Historiska Foton mot ett ArcGIS-linjelager (FeatureServer).

Hämtar linjelagret (via inloggad ArcGIS Pro-session), laddar ner varje foto från
fältet `foto_referens`, skalar ner det, och skriver om assets/foton.csv. Manuella
trim-värden (distans/bredd/hojd/rot/elev) i en befintlig foton.csv BEVARAS per
bildnamn.

KONFIGURATION (läggs INTE i repot):
  Skapa tools/sync.config.json (se sync.config.example.json), eller sätt
  miljövariabeln AR_FEATURESERVER_URL. Filen är gitignorerad så att
  serveradress och tjänstestruktur aldrig hamnar i versionshanteringen.

KÖR i ArcGIS Pro:s medföljande Python (propy) medan du är inloggad mot din portal.
"""
import io
import os
import re
import json
import arcpy
from urllib.request import urlopen, Request
from urllib.parse import urlencode
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
FOTON_DIR = os.path.join(REPO, "assets", "foton")
CSV_PATH = os.path.join(REPO, "assets", "foton.csv")
MAXPIX = 1600
DEFAULTS = {"elev": "", "distans": "12", "bredd": "16", "hojd": "1.6",
            "rot": "0", "sido": "0", "tilt": "0"}

HEADER = ("# AR Historiska Foton – Sommargatan\n"
          "# Genererad av tools/sync_from_featureserver.py. Manuella trim-värden\n"
          "# (distans/bredd/hojd/rot/sido/tilt/elev) bevaras per bildnamn vid ny synk.\n"
          "# Första raden = origo + fotstegsbäring för hela vyn.\n"
          "namn,lat1,lon1,lat2,lon2,elev,distans,bredd,hojd,rot,sido,tilt\n")


def load_config():
    """FeatureServer-URL + lager-id ur miljövariabel eller lokal (gitignorerad) config."""
    url = os.environ.get("AR_FEATURESERVER_URL")
    layer = os.environ.get("AR_FEATURESERVER_LAYER")
    cfg_path = os.path.join(HERE, "sync.config.json")
    if os.path.exists(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        url = url or cfg.get("featureServerUrl")
        if layer is None:
            layer = cfg.get("layerId")
    if not url:
        raise SystemExit(
            "Saknar FeatureServer-URL. Skapa tools/sync.config.json "
            "(kopiera sync.config.example.json) eller sätt "
            "miljövariabeln AR_FEATURESERVER_URL.")
    return url.rstrip("/"), int(layer) if layer is not None else 0


def token():
    t = arcpy.GetSigninToken()
    if not t:
        raise SystemExit("Ingen sign-in-token. Logga in mot din portal i ArcGIS Pro.")
    return t["token"]


def api(url, params, tok):
    params = dict(params); params["f"] = "json"; params["token"] = tok
    return json.loads(urlopen(url + "?" + urlencode(params), timeout=60).read().decode("utf-8"))


def load_existing_tuning():
    keep = {}
    if not os.path.exists(CSV_PATH):
        return keep
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            c = [x.strip() for x in line.split(",")]
            if c[0].lower() in ("namn", "name") or len(c) < 10:
                continue
            keep[c[0]] = {"elev": c[5], "distans": c[6], "bredd": c[7],
                          "hojd": c[8], "rot": c[9],
                          "sido": c[10] if len(c) > 10 else "0",
                          "tilt": c[11] if len(c) > 11 else "0"}
    return keep


def media_id(url):
    m = re.search(r"/image/([^/?]+)", url or "")
    return m.group(1) if m else None


def download_photo(url, dest):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (AR-sync)"})
    data = urlopen(req, timeout=90).read()
    im = Image.open(io.BytesIO(data)).convert("RGB")
    w, h = im.size
    if max(w, h) > MAXPIX:
        s = MAXPIX / float(max(w, h))
        im = im.resize((int(w * s), int(h * s)), Image.LANCZOS)
    im.save(dest, "JPEG", quality=82, optimize=True)
    return im.size


def main():
    base, layer = load_config()
    tok = token()
    if not os.path.isdir(FOTON_DIR):
        os.makedirs(FOTON_DIR)
    tuning = load_existing_tuning()

    # Lagret lagras i SWEREF 99 15 00 (EPSG:3007). outSR=4326 gör att servern
    # omprojicerar geometrin till WGS84 (lon/lat i grader), vilket appens
    # surveyOffset förutsätter. Rör inte outSR utan att ändra appens matematik.
    q = api(base + "/%d/query" % layer,
            {"where": "1=1", "outFields": "*", "returnGeometry": "true",
             "outSR": "4326", "orderByFields": "objectid"}, tok)
    if "error" in q:
        raise SystemExit("Query-fel: %s" % q["error"])
    feats = q.get("features", [])
    field_names = [f["name"] for f in q.get("fields", [])]
    has_bildfil = "bildfil" in field_names
    print("Hämtade %d features. bildfil-fält i tjänsten: %s"
          % (len(feats), "JA" if has_bildfil else "nej"))

    rows = []
    for ft in feats:
        attrs = ft.get("attributes", {})
        paths = ft.get("geometry", {}).get("paths", [])
        if not paths or len(paths[0]) < 2:
            print("  HOPPAR objectid=%s: linjen saknar 2 punkter" % attrs.get("objectid"))
            continue
        p1, p2 = paths[0][0], paths[0][1]           # [lon, lat]
        ref = attrs.get("foto_referens")

        if has_bildfil and attrs.get("bildfil"):
            namn = attrs["bildfil"]
        else:
            mid = media_id(ref)
            if not mid:
                print("  HOPPAR objectid=%s: kan ej härleda filnamn" % attrs.get("objectid"))
                continue
            namn = mid + ".jpg"

        dest = os.path.join(FOTON_DIR, namn)
        if os.path.exists(dest):
            print("  %s: finns redan, laddar EJ ner igen" % namn)
        elif ref:
            try:
                print("  %s: nedladdad %s" % (namn, download_photo(ref, dest)))
            except Exception as e:
                print("  %s: NEDLADDNING MISSLYCKADES (%s) – rad skrivs ändå" % (namn, e))
        else:
            print("  %s: saknar foto_referens" % namn)

        t = tuning.get(namn, DEFAULTS)
        rows.append([namn, "%.13f" % p1[1], "%.13f" % p1[0], "%.13f" % p2[1], "%.13f" % p2[0],
                     t["elev"], t["distans"], t["bredd"], t["hojd"], t["rot"],
                     t.get("sido", "0"), t.get("tilt", "0")])

    with open(CSV_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(HEADER)
        for r in rows:
            f.write(",".join(r) + "\n")
    print("Skrev %d rader till %s" % (len(rows), os.path.relpath(CSV_PATH, REPO)))


if __name__ == "__main__":
    main()
