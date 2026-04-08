from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import anthropic
import os

app = FastAPI(title="HealthHorizon API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


@app.get("/")
def root():
    return {"status": "ok", "service": "HealthHorizon PNRR API"}


@app.post("/analyze")
async def analyze(payload: dict):
    """
    Analisi AI documenti PNRR.
    payload: { messages: [...], system: str }
    """
    messages = payload.get("messages", [])
    system = payload.get("system", "Sei un esperto PNRR Missione 6 Salute. Rispondi in italiano.")

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=2048,
        system=system,
        messages=messages
    )

    return {
        "content": response.content[0].text,
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens
        }
    }
