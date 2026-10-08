from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import anthropic
import os

from limits import rate_limit, try_consume_ai_call, ai_usage
import costs
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
SYSTEM_PROMPT = (
    "Sei un esperto PNRR Missione 6 Salute e rendicontazione fondi pubblici europei. "
    "Rispondi sempre in italiano. Usa un linguaggio professionale ma chiaro. "
    "Fornisci analisi concrete con riferimenti normativi. "
    "Usa ⚠️ per criticità, ✅ per elementi positivi, 🔴 per urgenze, 📋 per checklist."
)
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
