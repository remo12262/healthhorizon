"""Dati delle misure M6 inseriti manualmente nell'app PNRR (pnrr.html), passati all'assistente.

Copia di MISURE (Tracker M6) e MISURE_DB (Calcolatore) di pnrr.html: se cambiano lì, vanno aggiornati qui.
Non sono aggiornati in automatico e non vengono da una fonte scaricata.
"""

# Tracker M6: dotazione complessiva (le scadenze sono state tolte: nessuna aveva una fonte registrata)
TRACKER = [
    ("Case della Comunità", "€2,0 Mld"),
    ("Ospedali di Comunità", "€1,0 Mld"),
    ("Centrali Operative Territoriali", "€0,3 Mld"),
    ("Telemedicina", "€1,0 Mld"),
    ("Ammodernamento tecnologico", "€4,05 Mld"),
    ("Fascicolo Sanitario Elettronico", "€1,38 Mld"),
]

# Calcolatore: misura, componente, importo per ente (min-max), documenti tipici
CALCOLATORE = [
    ("Case della Comunità", "M6C1 — Misura 1.1", "500.000–2.000.000 €",
     ["Progetto esecutivo", "CUP", "Accordo con MMG", "Planimetrie"]),
    ("Ospedali di Comunità", "M6C1 — Misura 1.3", "400.000–2.000.000 €",
     ["Progetto strutturale", "Delibera aziendale", "Piano gestionale", "CUP"]),
    ("Centrale Operativa Territoriale", "M6C1 — Misura 1.2", "100.000–500.000 €",
     ["Piano operativo", "Accordo interistituzionale", "Profili professionali"]),
    ("Piattaforme Telemedicina", "M6C1 — Misura 1.2.3", "200.000–3.000.000 €",
     ["Capitolato tecnico", "Piano formazione", "DPIA privacy", "Accordo con MMG"]),
    ("Grandi Apparecchiature (TAC/RM/AL)", "M6C2 — Misura 1.1", "500.000–8.000.000 €",
     ["Progetto di acquisto", "Piano installazione", "Collaudo impianti", "CUP"]),
    ("Fascicolo Sanitario Elettronico 2.0", "M6C2 — Misura 1.3", "100.000–500.000 €",
     ["Piano di adeguamento IT", "Accordo regionale", "Nomina DPO", "Cronoprogramma"]),
    ("Sicurezza e adeguamento strutturale", "M6C2 — Misura 1.2", "300.000–4.000.000 €",
     ["Progetto strutturale", "VVF", "Collaudo tecnico-amministrativo", "CUP"]),
]


def as_text() -> str:
    lines = ["Tracker M6 (dotazione complessiva):"]
    lines += [f"- {n}: {imp}" for n, imp in TRACKER]
    lines.append("Calcolatore di eligibilità (componente, importo per ente, documenti tipici):")
    lines += [f"- {n} ({comp}): {imp}; documenti: {', '.join(docs)}"
              for n, comp, imp, docs in CALCOLATORE]
    lines.append("Scadenze: nessuna nei dati dell'app. Le scadenze delle misure vanno verificate su Italia Domani "
                 "e sugli avvisi della propria Regione.")
    return "\n".join(lines)
