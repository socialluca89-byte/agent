"""
Job Search Agent - Cerca offerte di lavoro per docenti, formatori,
social media manager e sviluppatori web/e-commerce.

Ricerca SOLO annunci con modalità da remoto / smart working / telelavoro.

Piattaforme supportate:
- Facebook Groups (via scraping pubblico)
- LinkedIn (via ricerca pubblica)
- Indeed Italia
- InfoJobs
- Subito.it (lavoro)
- Bakeca.it (lavoro)
"""

import os
import json
import time
import asyncio
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

import anthropic
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

load_dotenv()

console = Console()

# Suffissi da remoto aggiunti automaticamente ad ogni keyword
REMOTE_SUFFIXES = [
    "da remoto",
    "smart working",
    "telelavoro",
    "lavoro remoto",
    "remote",
]

# Parole chiave per le categorie di interesse (sempre combinate con REMOTE_SUFFIXES)
SEARCH_KEYWORDS = {
    "docente_formatore": [
        "docente informatica",
        "formatore corsi",
        "insegnante informatica",
        "docente corsi formazione",
        "formatore aziendale",
        "trainer informatica",
        "docente e-learning",
        "istruttore corsi",
        "tutor online",
        "docente academy",
    ],
    "social_media": [
        "social media manager",
        "social media specialist",
        "community manager",
        "digital marketing",
        "content creator",
        "content manager",
        "social media marketing",
        "instagram manager",
        "facebook ads specialist",
        "copywriter digitale",
    ],
    "web_ecommerce": [
        "sviluppatore web",
        "web developer",
        "creazione siti web",
        "e-commerce manager",
        "wordpress developer",
        "shopify developer",
        "woocommerce",
        "sviluppatore ecommerce",
        "front end developer",
        "web designer",
    ],

}

# Termini che identificano il lavoro da remoto negli annunci
REMOTE_TERMS = {
    "da remoto", "remoto", "remote", "smart working", "telelavoro",
    "lavoro da casa", "home working", "full remote", "100% remoto",
    "completamente remoto", "lavoro online",
}

# URL base delle piattaforme — i parametri remoto/smart-working sono inclusi dove supportato
PLATFORMS = {
    # sc=0&remotejob=032b3046-06a3-4876-8dfd-474eb5e7ed11 = filtro "Lavoro da remoto" di Indeed
    "indeed": "https://it.indeed.com/jobs?q={query}&sc=0&remotejob=032b3046-06a3-4876-8dfd-474eb5e7ed11",
    # f_WT=2 = filtro "Remote" di LinkedIn
    "linkedin": "https://www.linkedin.com/jobs/search/?keywords={query}&location=Italia&f_WT=2",
    "infojobs": "https://www.infojobs.it/jobsearch/search-results/list.xhtml?keyword={query}&telecommuting=YES",
    "subito": "https://www.subito.it/annunci-italia/vendita/lavoro/?q={query}+remoto",
    "bakeca": "https://www.bakeca.it/annunci/offerte-di-lavoro/?q={query}+smart+working",
    "facebook_groups": [
        "https://www.facebook.com/groups/cercasilavoro.it",
        "https://www.facebook.com/groups/lavoroitalia",
        "https://www.facebook.com/groups/offertedilavoro.it",
        "https://www.facebook.com/groups/lavoro.formazione",
        "https://www.facebook.com/groups/digitalmarketingitalia",
        "https://www.facebook.com/groups/smartworkingitalia",
        "https://www.facebook.com/groups/lavorodacaremoto",
    ],
}


def get_client() -> anthropic.Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY non trovata nel file .env")
    return anthropic.Anthropic(api_key=api_key)


def build_search_urls(category: str | None = None, remote_only: bool = True) -> list[dict]:
    """Costruisce la lista di URL di ricerca per tutte le piattaforme.

    Se remote_only=True (default) aggiunge il suffisso 'da remoto' alla keyword
    per le piattaforme che non hanno un filtro nativo, assicurando che la ricerca
    sia orientata esclusivamente a posizioni remote/smart working.
    """
    urls = []
    categories = [category] if category else list(SEARCH_KEYWORDS.keys())

    for cat in categories:
        keywords = SEARCH_KEYWORDS.get(cat, [])
        for kw in keywords[:3]:  # Usa le prime 3 keyword per categoria
            # Per le piattaforme senza filtro nativo remoto, appende il suffisso
            search_kw = f"{kw} da remoto" if remote_only else kw
            encoded = search_kw.replace(" ", "+")
            for platform, url_template in PLATFORMS.items():
                if platform == "facebook_groups":
                    for group_url in url_template:
                        urls.append({
                            "platform": "Facebook Groups",
                            "category": cat,
                            "keyword": search_kw,
                            "url": group_url,
                            "remote_only": remote_only,
                        })
                else:
                    urls.append({
                        "platform": platform.capitalize(),
                        "category": cat,
                        "keyword": search_kw,
                        "url": url_template.format(query=encoded),
                        "remote_only": remote_only,
                    })
    return urls


# ── Tool definitions ─────────────────────────────────────────────────────────

def tool_fetch_job_listings(platform: str, url: str, keyword: str) -> dict:
    """Simula il fetch di annunci da una piattaforma (stub per demo senza browser)."""
    import requests
    from bs4 import BeautifulSoup

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        page_text = soup.get_text(separator="\n", strip=True)
        # Tronca per non superare i token limit
        page_text = page_text[:6000]
        return {
            "success": True,
            "platform": platform,
            "url": url,
            "keyword": keyword,
            "content": page_text,
            "status_code": response.status_code,
        }
    except Exception as e:
        return {
            "success": False,
            "platform": platform,
            "url": url,
            "keyword": keyword,
            "error": str(e),
            "content": "",
        }


def tool_extract_jobs(raw_content: str, platform: str, keyword: str) -> dict:
    """Estrae e struttura gli annunci di lavoro dal testo grezzo della pagina."""
    return {
        "raw_content": raw_content,
        "platform": platform,
        "keyword": keyword,
        "instruction": (
            "Analizza il testo della pagina ed estrai tutti gli annunci di lavoro "
            "pertinenti. Per ogni annuncio restituisci: titolo, azienda (se presente), "
            "luogo, modalita_lavoro (remoto/ibrido/presenza), tipo contratto (se indicato), "
            "descrizione breve, url annuncio (se presente). "
            "Includi il campo 'is_remote': true se l'annuncio menziona termini come "
            "'da remoto', 'smart working', 'telelavoro', 'remote', 'lavoro da casa', "
            "'full remote', 'home working', '100% remoto'. "
            "Se non è esplicitamente indicato come remoto, imposta is_remote: false."
        ),
    }


def tool_filter_jobs(jobs: list[dict], min_relevance: float = 0.6, remote_only: bool = True) -> dict:
    """Filtra i job per rilevanza e modalità remoto."""
    return {
        "jobs": jobs,
        "min_relevance": min_relevance,
        "remote_only": remote_only,
        "categories": list(SEARCH_KEYWORDS.keys()),
        "remote_terms": list(REMOTE_TERMS),
        "instruction": (
            "Filtra questi annunci applicando DUE criteri in AND:\n"
            "1. RILEVANZA >= "
            f"{min_relevance} rispetto alle categorie: docente/formatore, "
            "social media manager, sviluppatore web/e-commerce. "
            "Assegna uno score 0-1 e una categoria a ciascuno.\n"
            "2. REMOTO: mantieni SOLO gli annunci dove is_remote=true "
            "OPPURE la descrizione contiene almeno uno di questi termini: "
            f"{', '.join(REMOTE_TERMS)}. "
            "Scarta tutti gli annunci che non specificano la possibilità di lavorare da remoto."
        ),
    }


def tool_save_results(jobs: list[dict], output_dir: str) -> dict:
    """Salva i risultati su file JSON e genera un report."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = Path(output_dir) / f"jobs_{timestamp}.json"

    remote_count = sum(1 for j in jobs if j.get("is_remote") or j.get("modalita_lavoro") == "remoto")

    report = {
        "timestamp": timestamp,
        "total_jobs": len(jobs),
        "remote_jobs": remote_count,
        "by_category": {},
        "by_platform": {},
        "jobs": jobs,
    }

    for job in jobs:
        cat = job.get("category", "altro")
        plat = job.get("platform", "sconosciuta")
        report["by_category"][cat] = report["by_category"].get(cat, 0) + 1
        report["by_platform"][plat] = report["by_platform"].get(plat, 0) + 1

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return {
        "saved": True,
        "filepath": str(filepath),
        "total_jobs": len(jobs),
        "remote_jobs": remote_count,
        "summary": report["by_category"],
    }


# ── Tool schemas per Claude ───────────────────────────────────────────────────

TOOLS: list[dict] = [
    {
        "name": "fetch_job_listings",
        "description": (
            "Recupera il contenuto HTML di una pagina di offerte di lavoro "
            "da una piattaforma specifica (Indeed, LinkedIn, Facebook, ecc.). "
            "Restituisce il testo grezzo della pagina."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {"type": "string", "description": "Nome della piattaforma"},
                "url": {"type": "string", "description": "URL da visitare"},
                "keyword": {"type": "string", "description": "Parola chiave cercata"},
            },
            "required": ["platform", "url", "keyword"],
        },
    },
    {
        "name": "extract_jobs",
        "description": (
            "Analizza il testo grezzo di una pagina web ed estrae gli annunci "
            "di lavoro strutturati (titolo, azienda, luogo, contratto, descrizione, url)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "raw_content": {"type": "string", "description": "Testo grezzo della pagina"},
                "platform": {"type": "string", "description": "Piattaforma di provenienza"},
                "keyword": {"type": "string", "description": "Keyword usata per la ricerca"},
            },
            "required": ["raw_content", "platform", "keyword"],
        },
    },
    {
        "name": "filter_jobs",
        "description": (
            "Filtra e classifica gli annunci estratti per rilevanza e modalità remoto. "
            "Mantiene solo gli annunci che sono DA REMOTO / smart working / telelavoro "
            "E pertinenti alle categorie: docente/formatore, social media manager, "
            "sviluppatore web/e-commerce. Assegna uno score 0-1."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "jobs": {
                    "type": "array",
                    "description": "Lista di annunci da filtrare",
                    "items": {"type": "object"},
                },
                "min_relevance": {
                    "type": "number",
                    "description": "Score minimo di rilevanza (0-1), default 0.6",
                },
                "remote_only": {
                    "type": "boolean",
                    "description": "Se true (default) esclude annunci non remoti",
                },
            },
            "required": ["jobs"],
        },
    },
    {
        "name": "save_results",
        "description": "Salva i risultati filtrati su file JSON e genera un report.",
        "input_schema": {
            "type": "object",
            "properties": {
                "jobs": {
                    "type": "array",
                    "description": "Lista finale degli annunci",
                    "items": {"type": "object"},
                },
                "output_dir": {
                    "type": "string",
                    "description": "Directory dove salvare i risultati",
                },
            },
            "required": ["jobs", "output_dir"],
        },
    },
]


# ── Tool dispatcher ───────────────────────────────────────────────────────────

def dispatch_tool(name: str, inputs: dict) -> Any:
    if name == "fetch_job_listings":
        return tool_fetch_job_listings(**inputs)
    if name == "extract_jobs":
        return tool_extract_jobs(**inputs)
    if name == "filter_jobs":
        return tool_filter_jobs(**inputs)
    if name == "save_results":
        return tool_save_results(**inputs)
    return {"error": f"Tool sconosciuto: {name}"}


# ── Agent loop ────────────────────────────────────────────────────────────────

def run_agent(category: str | None = None, max_urls: int = 6, remote_only: bool = True) -> None:
    client = get_client()
    output_dir = os.getenv("OUTPUT_DIR", "results")

    urls = build_search_urls(category, remote_only=remote_only)[:max_urls]

    console.print(Panel.fit(
        "[bold cyan]Job Search Agent[/bold cyan]\n"
        "Categorie: docente/formatore · social media · web/e-commerce\n"
        "[bold yellow]Filtro: SOLO offerte DA REMOTO / smart working / telelavoro[/bold yellow]\n"
        f"URL da analizzare: {len(urls)}",
        border_style="cyan",
    ))

    # Costruisce il prompt di sistema
    system_prompt = """Sei un agente specializzato nella ricerca di offerte di lavoro italiane DA REMOTO.
Il tuo obiettivo è trovare SOLO annunci con modalità remota (smart working, telelavoro, lavoro da casa, remote)
per queste tre categorie:
1. Docenti / Formatori (informatica, corsi aziendali, e-learning, academy)
2. Social Media Manager / Digital Marketing (SMM, content creator, community manager)
3. Sviluppatori Web / E-commerce (WordPress, Shopify, WooCommerce, frontend)

REGOLA FONDAMENTALE: scarta qualsiasi annuncio che NON menziona esplicitamente la possibilità
di lavorare da remoto, in smart working, telelavoro o modalità equivalente.

Processo da seguire per ogni URL nella lista:
1. Usa fetch_job_listings per recuperare il contenuto della pagina
2. Usa extract_jobs per estrarre gli annunci strutturati dal testo (includi campo is_remote e modalita_lavoro)
3. Dopo aver raccolto tutti gli annunci, usa filter_jobs con remote_only=true
4. Infine usa save_results per salvare i risultati

Sii preciso nell'estrazione: cattura titolo, azienda, luogo, modalita_lavoro, tipo contratto e URL annuncio.
Se una pagina non carica o non contiene annunci pertinenti, passa alla successiva senza fermarti."""

    # Messaggio iniziale con la lista degli URL
    urls_text = "\n".join(
        f"- [{u['platform']}] {u['keyword']}: {u['url']}" for u in urls
    )
    user_message = (
        f"Cerca offerte di lavoro su queste piattaforme e URL:\n\n{urls_text}\n\n"
        f"Salva i risultati in: {output_dir}\n"
        "Procedi con la ricerca sistematica."
    )

    messages = [{"role": "user", "content": user_message}]

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Avvio ricerca...", total=None)

        iteration = 0
        max_iterations = 30  # Limite di sicurezza

        while iteration < max_iterations:
            iteration += 1
            progress.update(task, description=f"Iterazione {iteration} — chiamata a Claude...")

            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=system_prompt,
                tools=TOOLS,
                messages=messages,
            )

            # Aggiunge la risposta dell'assistente ai messaggi
            messages.append({"role": "assistant", "content": response.content})

            # Se nessun tool use, l'agent ha finito
            if response.stop_reason == "end_turn":
                progress.update(task, description="[green]Completato!")
                # Stampa il messaggio finale
                for block in response.content:
                    if hasattr(block, "text"):
                        console.print(Panel(block.text, title="Riepilogo finale", border_style="green"))
                break

            # Gestisce i tool use
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                tool_name = block.name
                tool_input = block.input
                progress.update(task, description=f"Tool: [yellow]{tool_name}[/yellow] ...")

                result = dispatch_tool(tool_name, tool_input)

                # Log sintetico a schermo
                if tool_name == "fetch_job_listings":
                    ok = result.get("success", False)
                    status = "[green]OK[/green]" if ok else "[red]ERRORE[/red]"
                    console.print(
                        f"  fetch [{status}] {result.get('platform')} — {result.get('keyword')}"
                    )
                elif tool_name == "save_results":
                    console.print(
                        f"  [bold green]Salvati {result.get('total_jobs', 0)} annunci[/bold green] "
                        f"→ {result.get('filepath')}"
                    )

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })

            if tool_results:
                messages.append({"role": "user", "content": tool_results})
            else:
                break

        else:
            console.print("[yellow]Raggiunto il limite di iterazioni.[/yellow]")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Job Search Agent — cerca offerte per docenti, SMM e sviluppatori web"
    )
    parser.add_argument(
        "--category",
        choices=list(SEARCH_KEYWORDS.keys()),
        default=None,
        help="Filtra per categoria specifica (default: tutte)",
    )
    parser.add_argument(
        "--max-urls",
        type=int,
        default=6,
        help="Numero massimo di URL da analizzare (default: 6)",
    )
    parser.add_argument(
        "--no-remote-filter",
        action="store_true",
        default=False,
        help="Disabilita il filtro remoto e cerca anche posizioni in presenza",
    )
    args = parser.parse_args()

    run_agent(category=args.category, max_urls=args.max_urls, remote_only=not args.no_remote_filter)


if __name__ == "__main__":
    main()
