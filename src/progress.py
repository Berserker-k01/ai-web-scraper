from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import List, Optional


@dataclass
class ScrapeProgress:
    status: str = "idle"
    message: str = ""
    start_url: str = ""
    current_url: str = ""
    current_page: int = 0
    companies_found: int = 0
    emails_found: int = 0
    phones_found: int = 0
    duplicates_skipped: int = 0
    profiles_visited: int = 0
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    output_dir: str = ""
    export_files: dict = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)
    recent_leads: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "message": self.message,
            "start_url": self.start_url,
            "current_url": self.current_url,
            "current_page": self.current_page,
            "companies_found": self.companies_found,
            "emails_found": self.emails_found,
            "phones_found": self.phones_found,
            "duplicates_skipped": self.duplicates_skipped,
            "profiles_visited": self.profiles_visited,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "output_dir": self.output_dir,
            "export_files": self.export_files,
            "issues": self.issues[-20:],
            "recent_leads": self.recent_leads,
        }


class ProgressTracker:
    def __init__(self) -> None:
        self._progress = ScrapeProgress()
        self._lock = Lock()

    @property
    def progress(self) -> ScrapeProgress:
        with self._lock:
            return self._progress

    def reset(self, start_url: str, output_dir: str) -> None:
        with self._lock:
            self._progress = ScrapeProgress(
                status="running",
                message="Démarrage du scraping...",
                start_url=start_url,
                current_url=start_url,
                started_at=datetime.now().isoformat(),
                output_dir=output_dir,
            )

    def update(self, **kwargs) -> None:
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self._progress, key):
                    setattr(self._progress, key, value)

    def add_issue(self, issue: str) -> None:
        with self._lock:
            self._progress.issues.append(issue)

    def add_recent_lead(self, row: dict) -> None:
        with self._lock:
            self._progress.recent_leads.append(row)
            self._progress.recent_leads = self._progress.recent_leads[-15:]

    def complete(self, export_files: dict, message: str = "Scraping terminé.") -> None:
        with self._lock:
            self._progress.status = "completed"
            self._progress.message = message
            self._progress.finished_at = datetime.now().isoformat()
            self._progress.export_files = export_files

    def fail(self, message: str) -> None:
        with self._lock:
            self._progress.status = "error"
            self._progress.message = message
            self._progress.finished_at = datetime.now().isoformat()

    def snapshot(self) -> dict:
        with self._lock:
            return self._progress.to_dict()
