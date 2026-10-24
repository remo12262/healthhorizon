"""Dati reali per il cruscotto: sorveglianza respiratoria ECDC (Italia), notizie ECDC, focolai OMS.

Fonti:
- ECDC ERVISS, dati settimanali per paese:
  https://github.com/EU-ECDC/Respiratory_viruses_weekly_data
- ECDC, notizie e Communicable Disease Threats Report (RSS)
- OMS, Disease Outbreak News (API pubblica)
Le fonti si riscaricano al massimo una volta al giorno (INTERVALLO_SECONDI) e l'ultima
copia viene salvata su file (CACHE_FILE). Se una fonte non risponde restano i dati
precedenti con la loro data. Dopo un riavvio si riparte dal file salvato o, se manca,
dalla copia di riserva nel repository (SEED_FILE). Nessuna chiamata all'AI.
"""
import asyncio
import csv
import io
import json
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx

ERVISS = "https://raw.githubusercontent.com/EU-ECDC/Respiratory_viruses_weekly_data/main/data"
ECDC_NEWS = "https://www.ecdc.europa.eu/en/taxonomy/term/1307/feed"
ECDC_CDTR = "https://www.ecdc.europa.eu/en/taxonomy/term/1505/feed"
WHO_DON = "https://www.who.int/api/news/diseaseoutbreaknews"
WHO_DON_PAGE = "https://www.who.int/emergencies/disease-outbreak-news/item/"
INTERVALLO_SECONDI = 24 * 3600
UA = {"User-Agent": "Mozilla/5.0 SentinellaAI/1.0 (+https://healthhorizon.it)"}

DATA_DIR = Path(__file__).parent / "data"
SEED_FILE = DATA_DIR / "sentinella_seed.json"
CACHE_FILE = Path(os.environ.get("SENTINELLA_CACHE_FILE", DATA_DIR / "sentinella_cache.json"))

# Descrizione delle fonti mostrata nel cruscotto (nome e link pubblico)
SOURCES = {
    "surveillance": {"name": "ECDC – ERVISS, dati settimanali per paese (Italia: rete RespiVirNet)",
                     "url": "https://github.com/EU-ECDC/Respiratory_viruses_weekly_data"},
    "ecdc": {"name": "ECDC – notizie e Communicable Disease Threats Report",
             "url": "https://www.ecdc.europa.eu/en/news-events"},
    "who": {"name": "OMS – Disease Outbreak News",
            "url": "https://www.who.int/emergencies/disease-outbreak-news"},
}

_cache = {"data": None}
_lock = asyncio.Lock()


def _week_key(yw: str):
    m = re.match(r"(\d{4})-W(\d{2})", yw)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def week_end(yw: str):
    """Domenica che chiude la settimana ISO, in formato AAAA-MM-GG."""
    y, w = _week_key(yw)
    try:
        return (date.fromisocalendar(y, w, 1) + timedelta(days=6)).isoformat()
    except ValueError:
        return None


def week_range(yw: str):
    """Date della settimana ISO, da lunedì a domenica: «23/02/2026 – 01/03/2026»."""
    y, w = _week_key(yw)
    try:
        start = date.fromisocalendar(y, w, 1)
    except ValueError:
        return None
    return f"{start:%d/%m/%Y} – {start + timedelta(days=6):%d/%m/%Y}"


def _weeks_ago(yw: str) -> int:
    y, w = _week_key(yw)
    try:
        then = date.fromisocalendar(y, w, 1)
    except ValueError:
        return 999
    return (date.today() - then).days // 7


async def _csv(client, name):
    r = await client.get(f"{ERVISS}/{name}.csv", headers=UA)
    r.raise_for_status()
    return [row for row in csv.DictReader(io.StringIO(r.text)) if row.get("countryname") == "Italy"]


def _rates(rows, indicator):
    """Serie settimanale nazionale (tutte le età), convertita in casi per 1.000 assistiti."""
    out = {}
    for r in rows:
        if r["indicator"] == indicator and r["age"] == "total":
            try:
                out[r["yearweek"]] = round(float(r["value"]) / 100, 2)
            except ValueError:
                pass
    return out


async def _erviss(client):
    ili_rows = await _csv(client, "ILIARIRates")
    pos_rows = await _csv(client, "sentinelTestsDetectionsPositivity")
    ili = _rates(ili_rows, "ILIconsultationrate")
    ari = _rates(ili_rows, "ARIconsultationrate")
    weeks = sorted(set(ili) | set(ari), key=_week_key)
    if not weeks:
        raise ValueError("nessun dato per l'Italia")
    last = weeks[-16:]

    def prev_season(yw):
        y, w = _week_key(yw)
        return f"{y - 1}-W{w:02d}"

    series = [{"week": w, "ili": ili.get(w), "ari": ari.get(w),
               "ili_prev": ili.get(prev_season(w)), "ari_prev": ari.get(prev_season(w))} for w in last]

    positivity = {}
    pos_weeks = sorted({r["yearweek"] for r in pos_rows if r["indicator"] == "positivity"}, key=_week_key)
    latest_pos = pos_weeks[-1] if pos_weeks else None
    for r in pos_rows:
        if r["yearweek"] == latest_pos and r["indicator"] == "positivity" and r["age"] == "total":
            key = {"Influenza": "influenza", "RSV": "rsv", "SARS-CoV-2": "sars_cov_2"}.get(r["pathogen"])
            if key and r["pathogensubtype"] in ("total", "RSV", "SARS-CoV-2"):
                try:
                    positivity[key] = float(r["value"])
                except ValueError:
                    pass
    latest = weeks[-1]
    # Dalla stagione 2025/26 l'Italia comunica ARI invece di ILI: si usa l'indicatore presente nell'ultima settimana
    indicator = "ari" if ari.get(latest) is not None else "ili"
    return {
        "indicator": indicator,
        "latest_week": latest,
        "weeks_since_latest": _weeks_ago(latest),
        "series": series,
        "positivity": positivity,
        "positivity_week": latest_pos,
        "unit": "casi per 1.000 assistiti a settimana",
    }


def _rss(text, limit):
    items = []
    for block in re.findall(r"<item>(.*?)</item>", text, re.S)[:limit]:
        title = re.search(r"<title>(.*?)</title>", block, re.S)
        link = re.search(r"<link>(.*?)</link>", block, re.S)
        pub = re.search(r"<pubDate>(.*?)</pubDate>", block, re.S)
        when = None
        if pub:
            try:
                when = datetime.strptime(pub.group(1).strip()[:16], "%a, %d %b %Y").date().isoformat()
            except ValueError:
                pass
        items.append({
            "title": re.sub(r"<!\[CDATA\[|\]\]>", "", title.group(1)).strip() if title else "",
            "url": link.group(1).strip() if link else "",
            "date": when,
        })
    return items


async def _ecdc(client):
    news = await client.get(ECDC_NEWS, headers=UA)
    cdtr = await client.get(ECDC_CDTR, headers=UA)
    news.raise_for_status()
    cdtr.raise_for_status()
    return {"news": _rss(news.text, 6), "threats_reports": _rss(cdtr.text, 3)}


async def _who(client):
    r = await client.get(WHO_DON, headers=UA, params={
        "$orderby": "PublicationDateAndTime desc", "$top": 6,
        "$select": "Title,PublicationDateAndTime,UrlName",
    })
    r.raise_for_status()
    return [{"title": x.get("Title", ""), "date": (x.get("PublicationDateAndTime") or "")[:10],
             "url": WHO_DON_PAGE + x.get("UrlName", "")} for x in r.json().get("value", [])]


def _data_date(key, payload):
    """Data a cui si riferisce il dato (non quella dello scarico)."""
    if not payload:
        return None
    if key == "surveillance":
        return week_end(payload["latest_week"])
    items = (payload.get("news", []) + payload.get("threats_reports", [])) if key == "ecdc" else payload
    dates = [n["date"] for n in items if n.get("date")]
    return max(dates) if dates else None


def _load_saved():
    """Ultima copia salvata: il file di cache se c'è, altrimenti la copia nel repository."""
    for f in (CACHE_FILE, SEED_FILE):
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
    return None


def _save(data):
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(CACHE_FILE)
    except OSError as e:
        print(f"[dati] copia non salvata: {e}")


async def download(prev: dict | None = None) -> dict:
    """Scarica tutte le fonti; quelle che non rispondono mantengono i dati e le date precedenti."""
    prev = prev or {}
    now = datetime.utcnow().isoformat(timespec="minutes")
    data = {"errors": {}, "sources": {}, "attempted_at": now}
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        for key, fn in (("surveillance", _erviss), ("ecdc", _ecdc), ("who", _who)):
            try:
                data[key] = await fn(client)
                downloaded = now
            except Exception as e:
                data["errors"][key] = f"{type(e).__name__}: {e}"[:200]
                data[key] = prev.get(key)
                downloaded = (prev.get("sources") or {}).get(key, {}).get("downloaded_at")
                print(f"[dati] ERRORE {key}: {data['errors'][key]}")
            data["sources"][key] = {**SOURCES[key], "downloaded_at": downloaded,
                                    "data_date": _data_date(key, data[key])}
    return data


def _age_seconds(data) -> float:
    try:
        return (datetime.utcnow() - datetime.fromisoformat(data["attempted_at"])).total_seconds()
    except (KeyError, TypeError, ValueError):
        return float("inf")


async def dashboard() -> dict:
    """Dati del cruscotto: riscaricati al massimo una volta al giorno, sempre con fonte e data."""
    if _cache["data"] is None:
        _cache["data"] = _load_saved()
    if _cache["data"] and _age_seconds(_cache["data"]) < INTERVALLO_SECONDI:
        return _cache["data"]
    async with _lock:
        if _cache["data"] and _age_seconds(_cache["data"]) < INTERVALLO_SECONDI:
            return _cache["data"]
        data = await download(_cache["data"])
        _cache["data"] = data
        _save(data)
    return data


def context_for_ai(d: dict) -> str:
    """Riassunto dei dati reali da passare all'AI, con le date di riferimento."""
    if not d:
        return ""
    lines = [f"DATI REALI DISPONIBILI (ultimo controllo delle fonti il {d.get('attempted_at')} UTC):"]
    s = d.get("surveillance")
    if s:
        last = s["series"][-1]
        ind = s.get("indicator", "ari")
        trend = ", ".join(f"{r['week']}: {r[ind]}" for r in s["series"][-6:] if r.get(ind) is not None)
        lines.append(
            f"- Sorveglianza respiratoria Italia (ECDC ERVISS / RespiVirNet), indicatore {ind.upper()} "
            f"({'infezioni respiratorie acute' if ind == 'ari' else 'sindromi simil-influenzali'}), {s['unit']}; "
            f"ultima settimana disponibile {s['latest_week']} ({s['weeks_since_latest']} settimane fa). Ultime settimane: {trend}.")
        if s.get("positivity"):
            p = s["positivity"]
            lines.append(f"- Positività dei campioni sentinella nella settimana {s['positivity_week']}: "
                         f"influenza {p.get('influenza')}%, RSV {p.get('rsv')}%, SARS-CoV-2 {p.get('sars_cov_2')}%.")
        if s["weeks_since_latest"] > 3:
            lines.append("- Il dato non è recente: il 9 marzo 2026 l'ISS ha comunicato che le Regioni hanno sospeso i flussi "
                         "di dati della sorveglianza RespiVirNet; da allora non ci sono nuovi dati italiani. "
                         "Non esistono soglie epidemiche ufficiali valide per l'indicatore ARI.")
    for n in (d.get("ecdc") or {}).get("news", [])[:5]:
        lines.append(f"- Notizia ECDC del {n['date']}: {n['title']} ({n['url']})")
    for n in (d.get("who") or [])[:4]:
        lines.append(f"- OMS Disease Outbreak News del {n['date']}: {n['title']} ({n['url']})")
    lines.append("Non sono disponibili dati su accessi in pronto soccorso, ricoveri o dati regionali italiani: non inventarli.")
    return "\n".join(lines)
