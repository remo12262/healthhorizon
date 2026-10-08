"""API di SentinellaAI ospitate nel backend HealthHorizon (prefisso /sentinella).

Il servizio separato sentinellaai-api non risponde: queste rotte lo sostituiscono con
lo stesso comportamento (chat, report, simulatore) più il cruscotto con dati reali.
"""
import os
from datetime import datetime

import anthropic
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import costs
import surveillance
from limits import rate_limit, try_consume_ai_call, ai_usage

router = APIRouter(prefix="/sentinella")
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
MODEL = "claude-haiku-4-5"
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")

LIMIT_MSG = ("Il servizio di analisi AI ha raggiunto il limite giornaliero di richieste. Riprova domani: "
             "i dati e i grafici della piattaforma restano consultabili.")
MAX_MESSAGE_CHARS = 4000
DISCLAIMER = ("\n\n---\n⚠️ SentinellaAI è un sistema prototipale. Dati da verificare su WHO.int, ECDC.europa.eu, ISS.it"
              " | Remo Pulcini — QuantumHorizon.it")


class ChatRequest(BaseModel):
    message: str
    mode: str = "chat"


class SimRequest(BaseModel):
    incremento: int
    durata: int
    copertura_vaccinale: int
    fascia_eta: str


@router.get("/health")
def health():
    return {"status": "ok", "service": "SentinellaAI", "web_search": "enabled" if TAVILY_API_KEY else "disabled",
            "ai_calls_today": ai_usage()}


@router.get("/api/dashboard")
async def dashboard():
    """Dati reali del cruscotto (ECDC, OMS) con data di riferimento e fonti."""
    return await surveillance.dashboard()


async def search_web(query: str) -> str:
    if not TAVILY_API_KEY:
        return ""
    try:
        async with httpx.AsyncClient(timeout=10.0) as h:
            r = await h.post("https://api.tavily.com/search", json={
                "api_key": TAVILY_API_KEY, "query": query, "max_results": 5, "include_answer": True})
            data = r.json()
        if not data.get("results"):
            return ""
        out = f"NOTIZIE WEB ({datetime.now().strftime('%d/%m/%Y')}):\n"
        if data.get("answer"):
            out += f"Sintesi: {data['answer']}\n\n"
        for i, res in enumerate(data["results"][:4], 1):
            out += f"{i}. {res.get('title', '')}\nFonte: {res.get('url', 'N/D')}\n{res.get('content', '')[:300]}\n\n"
        return out
    except Exception as e:
        print(f"[sentinella] TAVILY ERROR: {type(e).__name__}: {e}")
        return ""


def _ask(system: str, content: str, label: str) -> str:
    try:
        resp = client.messages.create(model=MODEL, max_tokens=1500, system=system,
                                      messages=[{"role": "user", "content": content}])
    except anthropic.APIError as e:
        print(f"[sentinella] ERRORE Claude ({label}): {type(e).__name__}: {e}")
        if "credit balance" in str(e).lower():
            raise HTTPException(503, "Analisi AI non disponibile: credito del servizio AI esaurito. I dati del cruscotto restano consultabili.")
        raise HTTPException(503, "Analisi AI momentaneamente non disponibile. Riprova tra qualche minuto.")
    costs.record(MODEL, resp, f"sentinella-{label}")
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")


@router.post("/api/chat", dependencies=[Depends(rate_limit)])
async def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(400, "Messaggio vuoto")
    if len(req.message) > MAX_MESSAGE_CHARS:
        raise HTTPException(400, f"Messaggio troppo lungo (massimo {MAX_MESSAGE_CHARS} caratteri).")
    if not try_consume_ai_call():
        return {"response": LIMIT_MSG}
    today = datetime.now().strftime("%d/%m/%Y")
    system = f"""Sei SentinellaAI, sistema prototipale di supporto alla sorveglianza epidemiologica, ideato e sviluppato da Remo Pulcini di QuantumHorizon.it. Data oggi: {today}.
Rispondi sempre in italiano professionale.
Nei report usa SEMPRE questa intestazione: 'SentinellaAI — Sistema sviluppato da Remo Pulcini | QuantumHorizon.it'.
Non fare MAI riferimento al Ministero della Salute come istituzione emittente.
REGOLE SUI DATI:
1. Cita numeri SOLO se presenti nei DATI REALI qui sotto o nelle notizie web, indicando fonte e settimana di riferimento.
2. Se mancano dati numerici scrivi 'dati non disponibili da fonti verificate'.
3. Persone esposte NON equivale a casi confermati.
4. Sii conciso — massimo 350 parole.
5. Non esistono dati su accessi in pronto soccorso, ricoveri o singole regioni: se richiesti, dillo e indica dove consultarli (RespiVirNet ISS, bollettini regionali)."""
    system += "\n\n" + surveillance.context_for_ai(await surveillance.dashboard())
    if req.mode == "report":
        system += f"\nGenera un report formale con sezioni numerate, data {today}."
    keywords = ["virus", "focolaio", "epidemia", "covid", "mpox", "dengue", "influenza", "ebola", "west nile", "oggi", "aggiornamento"]
    web = await search_web(req.message + " epidemia salute") if any(k in req.message.lower() for k in keywords) else ""
    msg = f"{web}\nRichiesta: {req.message}" if web else req.message
    return {"response": _ask(system, msg, req.mode) + DISCLAIMER}


@router.post("/api/simulate", dependencies=[Depends(rate_limit)])
async def simulate(req: SimRequest):
    if not try_consume_ai_call():
        return {"response": LIMIT_MSG}
    today = datetime.now().strftime("%d/%m/%Y")
    context = surveillance.context_for_ai(await surveillance.dashboard())
    prompt = (f"Scenario ipotetico al {today}: aumento del {req.incremento}% dell'incidenza delle infezioni respiratorie, "
              f"durata {req.durata} settimane, copertura vaccinale {req.copertura_vaccinale}%, fascia d'età {req.fascia_eta}. "
              "Parti dall'ultimo dato reale disponibile indicato sotto (dichiarando la settimana di riferimento) e descrivi "
              "in modo qualitativo l'impatto atteso su casi, ricoveri, pronto soccorso e saturazione, con una raccomandazione. "
              "Chiarisci che è una proiezione ragionata e non un modello epidemiologico validato; non presentare stime come dati.\n\n"
              + context)
    system = "Sei SentinellaAI sviluppato da Remo Pulcini di QuantumHorizon.it. Rispondi in italiano professionale."
    return {"response": _ask(system, prompt, "simulate") + DISCLAIMER}
