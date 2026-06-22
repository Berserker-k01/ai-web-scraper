import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, HttpUrl

from config import API_TOKEN
from src.lead_scraper import LeadScraper
from src.progress import ProgressTracker

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory="templates")

DOWNLOAD_FORMATS = {"csv", "xlsx", "json"}


@dataclass
class JobState:
    tracker: ProgressTracker
    output_dir: Optional[Path] = None
    task: Optional[asyncio.Task] = None
    url: str = ""


jobs: Dict[str, JobState] = {}
active_job_id: Optional[str] = None


class ScrapeRequest(BaseModel):
    url: HttpUrl
    max_pages: int = Field(default=100, ge=1, le=500)


app = FastAPI(title="B2B Lead Scraper")


def _download_urls(job_id: str) -> dict:
    return {
        fmt: f"/api/download/{job_id}/{fmt}"
        for fmt in DOWNLOAD_FORMATS
    }


def _progress_payload(job_id: str, state: JobState) -> dict:
    data = state.tracker.snapshot()
    if state.output_dir and data.get("companies_found", 0) > 0:
        data["export_files"] = _download_urls(job_id)
        data["downloads_ready"] = True
    else:
        data["downloads_ready"] = False
    data["job_id"] = job_id
    return data


async def _run_scrape(job_id: str, url: str, max_pages: int) -> None:
    global active_job_id
    state = jobs[job_id]
    scraper = LeadScraper(progress=state.tracker)

    try:
        leads = await scraper.run(url, max_pages=max_pages)
        state.output_dir = scraper._output_dir
        export_files = _download_urls(job_id)
        state.tracker.complete(
            export_files,
            message=f"Terminé — {len(leads)} entreprises exportées.",
        )
        logger.info("Job %s terminé : %s entreprises", job_id, len(leads))
    except Exception as exc:
        logger.exception("Job %s en erreur", job_id)
        if scraper._output_dir:
            state.output_dir = scraper._output_dir
        if state.tracker.progress.status != "error":
            state.tracker.fail(str(exc))
    finally:
        active_job_id = None


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "has_api_key": bool(API_TOKEN)},
    )


@app.get("/api/health")
async def health():
    return {"status": "ok", "api_key_configured": bool(API_TOKEN)}


@app.post("/api/scrape")
async def start_scrape(body: ScrapeRequest):
    global active_job_id

    if not API_TOKEN:
        return JSONResponse(
            status_code=400,
            content={"error": "DEEPSEEK_API_KEY manquante. Ajoutez-la dans le fichier .env"},
        )

    if active_job_id:
        active = jobs.get(active_job_id)
        if active and active.tracker.progress.status == "running":
            return JSONResponse(
                status_code=409,
                content={
                    "error": "Un scraping est déjà en cours.",
                    "job_id": active_job_id,
                },
            )

    job_id = str(uuid.uuid4())
    tracker = ProgressTracker()
    jobs[job_id] = JobState(tracker=tracker, url=str(body.url))

    task = asyncio.create_task(
        _run_scrape(job_id, str(body.url), body.max_pages),
        name=f"scrape-{job_id}",
    )
    jobs[job_id].task = task
    active_job_id = job_id

    return {"job_id": job_id, "status": "started"}


@app.get("/api/progress/{job_id}")
async def get_progress(job_id: str):
    state = jobs.get(job_id)
    if not state:
        return JSONResponse(status_code=404, content={"error": "Job introuvable"})
    return _progress_payload(job_id, state)


@app.get("/api/leads/{job_id}")
async def get_leads(job_id: str, limit: int = 100, offset: int = 0):
    state = jobs.get(job_id)
    if not state:
        return JSONResponse(status_code=404, content={"error": "Job introuvable"})

    leads_path = _resolve_export_path(state, "json")
    if leads_path and leads_path.exists():
        data = json.loads(leads_path.read_text(encoding="utf-8"))
        slice_data = data[offset : offset + limit]
        return {
            "total": len(data),
            "offset": offset,
            "limit": limit,
            "leads": slice_data,
        }

    snapshot = state.tracker.snapshot()
    return {
        "total": snapshot.get("companies_found", 0),
        "offset": 0,
        "limit": limit,
        "leads": snapshot.get("recent_leads", [])[:limit],
    }


@app.get("/api/download/{job_id}/{fmt}")
async def download_export(job_id: str, fmt: str):
    if fmt not in DOWNLOAD_FORMATS:
        return JSONResponse(status_code=400, content={"error": "Format invalide"})

    state = jobs.get(job_id)
    if not state:
        return JSONResponse(status_code=404, content={"error": "Job introuvable"})

    file_path = _resolve_export_path(state, fmt)
    if not file_path or not file_path.exists():
        return JSONResponse(
            status_code=404,
            content={"error": "Fichier non disponible (scraping en cours ou vide)"},
        )

    media_types = {
        "csv": "text/csv",
        "json": "application/json",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    return FileResponse(
        file_path,
        media_type=media_types[fmt],
        filename=f"leads.{fmt}",
    )


@app.get("/api/jobs")
async def list_jobs():
    return {
        job_id: _progress_payload(job_id, state)
        for job_id, state in jobs.items()
    }


def _resolve_export_path(state: JobState, fmt: str) -> Optional[Path]:
    if state.output_dir:
        path = state.output_dir / f"leads.{fmt}"
        if path.exists():
            return path

    output_dir = state.tracker.progress.output_dir
    if output_dir:
        path = Path(output_dir) / f"leads.{fmt}"
        if path.exists():
            state.output_dir = Path(output_dir)
            return path

    return None


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000)
