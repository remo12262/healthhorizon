"""Dati delle misure M6 inseriti manualmente nell'app PNRR (pnrr.html), passati all'assistente.

Copia di MISURE (Tracker M6) e MISURE_DB (Calcolatore) di pnrr.html: se cambiano lì, vanno aggiornati qui.
Non sono aggiornati in automatico e non vengono da una fonte scaricata.
"""

# Tracker M6: dotazione complessiva e scadenza indicativa
TRACKER = [
    ("Case della Comunità", "€2,0 Mld", "Dic 2026"),
    ("Ospedali di Comunità", "€1,0 Mld", "Dic 2026"),
    ("Centrali Operative Territoriali", "€0,3 Mld", "Giu 2026"),
    ("Telemedicina", "€1,0 Mld", "Set 2025"),
    ("Ammodernamento tecnologico", "€4,05 Mld", "Mar 2026"),
    ("Fascicolo Sanitario Elettronico", "€1,38 Mld", "Dic 2025"),
]

# Calcolatore: misura, componente, importo per ente (min-max), scadenza, documenti tipici
CALCOLATORE = [
    ("Case della Comunità", "M6C1 — Misura 1.1", "500.000–2.000.000 €", "31 Dicembre 2026",
     ["Progetto esecutivo", "CUP", "Accordo con MMG", "Planimetrie"]),
    ("Ospedali di Comunità", "M6C1 — Misura 1.3", "400.000–2.000.000 €", "31 Dicembre 2026",
     ["Progetto strutturale", "Delibera aziendale", "Piano gestionale", "CUP"]),
    ("Centrale Operativa Territoriale", "M6C1 — Misura 1.2", "100.000–500.000 €", "30 Giugno 2026",
     ["Piano operativo", "Accordo interistituzionale", "Profili professionali"]),
    ("Piattaforme Telemedicina", "M6C1 — Misura 1.2.3", "200.000–3.000.000 €", "30 Settembre 2025",
     ["Capitolato tecnico", "Piano formazione", "DPIA privacy", "Accordo con MMG"]),
    ("Grandi Apparecchiature (TAC/RM/AL)", "M6C2 — Misura 1.1", "500.000–8.000.000 €", "31 Marzo 2026",
     ["Progetto di acquisto", "Piano installazione", "Collaudo impianti", "CUP"]),
    ("Fascicolo Sanitario Elettronico 2.0", "M6C2 — Misura 1.3", "100.000–500.000 €", "31 Dicembre 2025",
     ["Piano di adeguamento IT", "Accordo regionale", "Nomina DPO", "Cronoprogramma"]),
    ("Sicurezza e adeguamento strutturale", "M6C2 — Misura 1.2", "300.000–4.000.000 €", "31 Dicembre 2026",
     ["Progetto strutturale", "VVF", "Collaudo tecnico-amministrativo", "CUP"]),
]


def as_text() -> str:
    lines = ["Tracker M6 (dotazione complessiva, scadenza indicativa):"]
    lines += [f"- {n}: {imp}, scadenza {sc}" for n, imp, sc in TRACKER]
    lines.append("Calcolatore di eligibilità (componente, importo per ente, scadenza, documenti tipici):")
    lines += [f"- {n} ({comp}): {imp}, scadenza {sc}; documenti: {', '.join(docs)}"
              for n, comp, imp, sc, docs in CALCOLATORE]
    return "\n".join(lines)
