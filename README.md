# HealthHorizon — PNRR Sanità Intelligence

Piattaforma a tre moduli per la PA italiana sul PNRR Missione 6 Salute.

## Struttura
```
healthhorizon/
├── index.html          ← Frontend completo (3 moduli)
└── backend/
    ├── main.py         ← FastAPI (analisi AI)
    └── requirements.txt
```

## Moduli
1. **Tracker M6** — Dashboard avanzamento misure e regioni (dati statici aggiornabili)
2. **Assistente AI** — Analisi documenti PNRR con Claude API
3. **Calcolatore Eligibilità** — Misure disponibili per tipo ente e parametri

---

## Deploy

### 1. GitHub
Crea repo `healthhorizon` sotto QuantumHorizon-IT.
Carica `index.html` nella root e cartella `backend/`.

### 2. Render — Backend (FastAPI)
- New Web Service → root: `backend`
- Build: `pip install -r requirements.txt`
- Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Plan: Starter ($7/mo)
- Env var: `ANTHROPIC_API_KEY`

### 3. Render — Frontend (Static Site)
- New Static Site → root: `.` (root del repo)
- Publish: `./`
- Modifica in `index.html` la riga:
  ```js
  const API_BASE = 'https://healthhorizon-api.onrender.com';
  ```

### 4. Dominio
Su Aruba acquista `healthhorizon.it`.
Aggiungi record DNS:
- A → `216.24.57.1` (root)
- CNAME www → URL Render Static Site

---

## Aggiornamento dati tracker
I dati delle misure e delle regioni sono in `index.html` nelle costanti:
- `MISURE` — le 6 componenti PNRR M6
- `REGIONI_DATA` — avanzamento per regione

Aggiorna i valori periodicamente consultando il portale **italiadomani.gov.it**.

---

## Note legali
I dati di avanzamento sono stime basate su fonti pubbliche (Italia Domani, Ministero Salute, AGENAS).
L'assistente AI è uno strumento di supporto: non sostituisce consulenza legale o amministrativa.
