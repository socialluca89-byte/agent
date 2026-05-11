"""
Interfaccia web per leggere, validare e candidarsi alle offerte di lavoro
trovate dal Job Search Agent.
"""

import json
import os
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template, request, jsonify, redirect, url_for
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
RESULTS_DIR = Path(os.getenv("OUTPUT_DIR", "results"))
VALIDATED_FILE = RESULTS_DIR / "validated.json"


def load_all_jobs() -> list[dict]:
    """Carica tutti gli annunci dai file JSON nella cartella results/."""
    all_jobs = []
    seen_ids = set()

    if not RESULTS_DIR.exists():
        return []

    for filepath in sorted(RESULTS_DIR.glob("jobs_*.json"), reverse=True):
        try:
            data = json.loads(filepath.read_text(encoding="utf-8"))
            for job in data.get("jobs", []):
                # ID univoco basato su titolo + azienda + piattaforma
                uid = f"{job.get('titolo','')}-{job.get('azienda','')}-{job.get('platform','')}".lower()
                if uid not in seen_ids:
                    seen_ids.add(uid)
                    job.setdefault("id", uid)
                    job.setdefault("source_file", filepath.name)
                    all_jobs.append(job)
        except Exception:
            continue

    return all_jobs


def load_validated() -> dict:
    """Carica lo stato di validazione (approvato/rifiutato/in attesa)."""
    if VALIDATED_FILE.exists():
        return json.loads(VALIDATED_FILE.read_text(encoding="utf-8"))
    return {}


def save_validated(data: dict) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    VALIDATED_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_result_files() -> list[dict]:
    if not RESULTS_DIR.exists():
        return []
    files = []
    for f in sorted(RESULTS_DIR.glob("jobs_*.json"), reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            files.append({
                "name": f.name,
                "total": data.get("total_jobs", 0),
                "remote": data.get("remote_jobs", 0),
                "timestamp": data.get("timestamp", ""),
            })
        except Exception:
            pass
    return files


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    jobs = load_all_jobs()
    validated = load_validated()
    stats = {
        "total": len(jobs),
        "approvati": sum(1 for v in validated.values() if v["status"] == "approvato"),
        "rifiutati": sum(1 for v in validated.values() if v["status"] == "rifiutato"),
        "in_attesa": sum(
            1 for j in jobs if validated.get(j["id"], {}).get("status") == "in_attesa"
            or j["id"] not in validated
        ),
    }
    category_filter = request.args.get("categoria", "")
    platform_filter = request.args.get("piattaforma", "")
    status_filter = request.args.get("stato", "")

    categories = sorted({j.get("category", "") for j in jobs if j.get("category")})
    platforms = sorted({j.get("platform", "") for j in jobs if j.get("platform")})

    filtered = jobs
    if category_filter:
        filtered = [j for j in filtered if j.get("category") == category_filter]
    if platform_filter:
        filtered = [j for j in filtered if j.get("platform") == platform_filter]
    if status_filter:
        if status_filter == "in_attesa":
            filtered = [j for j in filtered if j["id"] not in validated or validated[j["id"]]["status"] == "in_attesa"]
        else:
            filtered = [j for j in filtered if validated.get(j["id"], {}).get("status") == status_filter]

    # Arricchisce con lo stato corrente
    for job in filtered:
        v = validated.get(job["id"], {})
        job["status"] = v.get("status", "in_attesa")
        job["note"] = v.get("note", "")
        job["messaggio"] = v.get("messaggio", "")

    result_files = get_result_files()

    return render_template(
        "index.html",
        jobs=filtered,
        stats=stats,
        categories=categories,
        platforms=platforms,
        categoria=category_filter,
        piattaforma=platform_filter,
        stato=status_filter,
        result_files=result_files,
    )


@app.route("/job/<path:job_id>")
def job_detail(job_id):
    jobs = load_all_jobs()
    job = next((j for j in jobs if j["id"] == job_id), None)
    if not job:
        return redirect(url_for("index"))

    validated = load_validated()
    v = validated.get(job_id, {})
    job["status"] = v.get("status", "in_attesa")
    job["note"] = v.get("note", "")
    job["messaggio"] = v.get("messaggio", generate_default_message(job))

    return render_template("job_detail.html", job=job)


@app.route("/api/validate", methods=["POST"])
def api_validate():
    data = request.get_json()
    job_id = data.get("id")
    status = data.get("status")  # approvato | rifiutato | in_attesa
    note = data.get("note", "")
    messaggio = data.get("messaggio", "")

    if not job_id or status not in ("approvato", "rifiutato", "in_attesa"):
        return jsonify({"ok": False, "error": "Dati non validi"}), 400

    validated = load_validated()
    validated[job_id] = {
        "status": status,
        "note": note,
        "messaggio": messaggio,
        "updated_at": datetime.now().isoformat(),
    }
    save_validated(validated)
    return jsonify({"ok": True})


@app.route("/api/message/generate", methods=["POST"])
def api_generate_message():
    data = request.get_json()
    job = data.get("job", {})
    msg = generate_default_message(job)
    return jsonify({"messaggio": msg})


@app.route("/candidature")
def candidature():
    jobs = load_all_jobs()
    validated = load_validated()
    approvati = [
        {**j, **validated[j["id"]]}
        for j in jobs
        if validated.get(j["id"], {}).get("status") == "approvato"
    ]
    return render_template("candidature.html", jobs=approvati)


def generate_default_message(job: dict) -> str:
    titolo = job.get("titolo", "la posizione")
    azienda = job.get("azienda", "")
    cat = job.get("category", "")

    firma = "[Il tuo nome]"

    if cat == "docente_formatore":
        competenze = "formazione informatica, didattica online e progettazione di percorsi formativi"
    elif cat == "social_media":
        competenze = "gestione social media, creazione contenuti e strategie di digital marketing"
    else:
        competenze = "sviluppo web, e-commerce (WordPress, Shopify, WooCommerce) e UI/UX"

    azienda_str = f" presso {azienda}" if azienda else ""

    return (
        f"Buongiorno,\n\n"
        f"Ho visto con interesse l'annuncio per {titolo}{azienda_str} "
        f"e mi piacerebbe candidarmi.\n\n"
        f"Ho esperienza in {competenze} e sono disponibile a lavorare completamente da remoto.\n\n"
        f"Sarei felice di condividere il mio portfolio/CV e di fissare una breve call conoscitiva "
        f"per valutare insieme una possibile collaborazione.\n\n"
        f"Resto a disposizione per qualsiasi informazione.\n\n"
        f"Cordiali saluti,\n{firma}"
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
