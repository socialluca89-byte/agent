# Job Search Agent

Agente AI che cerca automaticamente offerte di lavoro su Facebook e altre piattaforme per queste categorie:

- **Docenti / Formatori** — corsi informatica, formazione aziendale, e-learning, academy
- **Social Media Manager** — SMM, content creator, community manager, digital marketing
- **Sviluppatori Web / E-commerce** — WordPress, Shopify, WooCommerce, frontend developer

## Piattaforme ricercate

| Piattaforma | Tipo |
|---|---|
| Facebook Groups | Gruppi pubblici lavoro |
| LinkedIn | Offerte di lavoro |
| Indeed Italia | Portale lavoro |
| InfoJobs | Portale lavoro |
| Subito.it | Annunci lavoro |
| Bakeca.it | Annunci lavoro |

## Setup

```bash
# 1. Installa le dipendenze
pip install -r requirements.txt

# 2. Configura le variabili d'ambiente
cp .env.example .env
# Modifica .env e inserisci la tua ANTHROPIC_API_KEY

# 3. (Opzionale) Installa i browser per Playwright
playwright install chromium
```

## Utilizzo

```bash
# Cerca in tutte le categorie (6 URL per default)
python job_search_agent.py

# Cerca solo docenti/formatori
python job_search_agent.py --category docente_formatore

# Cerca solo social media manager
python job_search_agent.py --category social_media

# Cerca solo sviluppatori web/e-commerce
python job_search_agent.py --category web_ecommerce

# Analizza più URL contemporaneamente
python job_search_agent.py --max-urls 15
```

## Output

I risultati vengono salvati in `results/jobs_YYYYMMDD_HHMMSS.json` con questa struttura:

```json
{
  "timestamp": "20260511_143000",
  "total_jobs": 42,
  "by_category": {
    "docente_formatore": 12,
    "social_media": 18,
    "web_ecommerce": 12
  },
  "by_platform": {
    "Indeed": 15,
    "Linkedin": 10,
    "Facebook Groups": 17
  },
  "jobs": [
    {
      "titolo": "Social Media Manager",
      "azienda": "Agenzia XYZ",
      "luogo": "Milano",
      "contratto": "Tempo indeterminato",
      "descrizione": "...",
      "url": "https://...",
      "platform": "Indeed",
      "category": "social_media",
      "relevance_score": 0.92
    }
  ]
}
```

## Architettura

L'agente usa il **Claude Sonnet 4.6** con tool use in un loop autonomo:

```
Claude ──► fetch_job_listings  (scarica pagina)
      ──► extract_jobs         (estrae annunci strutturati)
      ──► filter_jobs          (filtra per rilevanza)
      ──► save_results         (salva JSON + report)
```

Ogni iterazione Claude decide autonomamente quale tool usare e in quale ordine, adattandosi ai risultati ottenuti.
