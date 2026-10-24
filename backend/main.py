from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import anthropic
import os

from limits import rate_limit, try_consume_ai_call, ai_usage
import costs
import pnrr_dataset
import sentinella

app = FastAPI(title="HealthHorizon API", version="1.1.0")

ALLOWED_ORIGINS = [
    "https://healthhorizon.it",
    "https://www.healthhorizon.it",
    "https://healthhorizon.onrender.com",
    "https://sentinellaai.onrender.com",
    "http://localhost:5173",
    "http://localhost:8000",
] + [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

MODEL = os.environ.get("PNRR_MODEL", "claude-opus-4-5")
# Frase fissa di rimando: il frontend la riconosce e mostra le fonti ufficiali
VERIFY_SENTENCE = ("Date, importi e riferimenti esatti vanno verificati su Italia Domani, sui decreti di riparto "
                   "e sugli avvisi della tua Regione: non dispongo dei documenti ufficiali.")
MANUAL_LABEL = "dato inserito manualmente nell'app, non aggiornato in automatico"

# L'assistente non ha davanti i documenti del PNRR: date, importi e norme li ricostruirebbe a memoria
SYSTEM_PROMPT = f"""Sei l'assistente di PNRR Sanità Intelligence: aiuti in termini generali enti sanitari e uffici
PNRR su progettazione, attuazione e rendicontazione della Missione 6 Salute.
Rispondi sempre in italiano, in modo professionale ma chiaro.
Usa ⚠️ per criticità, ✅ per elementi positivi, 🔴 per urgenze, 📋 per checklist.

Non hai davanti decreti, circolari, milestone, target né avvisi ufficiali. Per questo valgono queste regole,
senza eccezioni:

1. Non scrivere MAI date, scadenze, importi, percentuali, numeri o codici di misura, milestone o target,
   né riferimenti normativi (decreti, DM, circolari, leggi, articoli) o titoli di atti, se non sono nei
   DATI DELL'APP qui sotto. Non scriverli neppure come esempio o tra parentesi.
2. Se un dato è nei DATI DELL'APP, puoi riportarlo SOLO indicando che proviene da lì, con questa
   avvertenza tra parentesi: "({MANUAL_LABEL})".
3. Per tutto il resto spiega procedure, documenti tipici e rischi in termini generali, e quando servirebbe
   un dato preciso o un riferimento scrivi esattamente questa frase, una sola volta, alla fine:
   "{VERIFY_SENTENCE}"
4. Non dichiarare mai di aver commesso un errore specifico in una risposta precedente e non proporre una
   versione "corretta" con dati nuovi. Se l'utente contesta, limitati a dire che non disponi dei documenti
   ufficiali e che il dato va verificato sulle fonti ufficiali, poi fermati.
5. Se l'utente cita nomi di file caricati, non ne conosci il contenuto: dillo.

DATI DELL'APP (inseriti manualmente, non aggiornati in automatico):
{pnrr_dataset.as_text()}"""
MAX_MESSAGES = 20
MAX_TOTAL_CHARS = 20000
LIMIT_MSG = (
    "L'assistente AI ha raggiunto il limite giornaliero di richieste. "
    "Riprova domani: il Tracker M6 e il Calcolatore di eligibilità restano consultabili."
)


# API di SentinellaAI (il servizio separato sentinellaai-api non risponde)
app.include_router(sentinella.router)


@app.get("/")
def root():
    return {"status": "ok", "service": "HealthHorizon PNRR API"}


@app.get("/health")
def health():
    return {"status": "ok", "ai_calls_today": ai_usage()}


@app.get("/ai-costs")
def ai_costs():
    """Registro dei costi giornalieri delle chiamate a Claude."""
    return costs.report()


def _clean_messages(raw) -> list:
    if not isinstance(raw, list) or not raw:
        raise HTTPException(400, "Nessun messaggio da analizzare.")
    messages = [
        {"role": m["role"], "content": m["content"]}
        for m in raw
        if isinstance(m, dict)
        and m.get("role") in ("user", "assistant")
        and isinstance(m.get("content"), str)
        and m["content"].strip()
    ][-MAX_MESSAGES:]
    while messages and messages[0]["role"] != "user":
        messages.pop(0)
    if not messages or messages[-1]["role"] != "user":
        raise HTTPException(400, "L'ultimo messaggio deve essere una domanda dell'utente.")
    if sum(len(m["content"]) for m in messages) > MAX_TOTAL_CHARS:
        raise HTTPException(400, "Conversazione troppo lunga: avvia una nuova analisi.")
    return messages


@app.post("/analyze", dependencies=[Depends(rate_limit)])
async def analyze(payload: dict):
    """
    Analisi AI documenti PNRR.
    payload: { messages: [{role, content}, ...] }. Il prompt di sistema è fissato dal server.
    """
    messages = _clean_messages(payload.get("messages"))
    if not try_consume_ai_call():
        return {"content": LIMIT_MSG, "limited": True}
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
    except anthropic.APIError as e:
        print(f"[analyze] Claude error: {type(e).__name__}: {e}")
        raise HTTPException(502, "Servizio AI momentaneamente non disponibile. Riprova tra qualche minuto.")
    costs.record(MODEL, response, "analyze")
    text = "".join(b.text for b in response.content if b.type == "text")
    return {
        "content": text,
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        },
    }
