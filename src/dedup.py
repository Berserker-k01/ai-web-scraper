import hashlib
import re
from typing import Optional
from urllib.parse import urlparse

from models.business import BusinessLead


def _normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def _domain_from_url(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def fingerprint(lead: BusinessLead) -> str:
    parts = [
        _normalize_name(lead.company_name),
        _domain_from_url(lead.website),
        (lead.phone or "").strip(),
        (lead.email or "").strip().lower(),
    ]
    raw = "|".join(parts)
    return hashlib.md5(raw.encode()).hexdigest()


class Deduplicator:
    def __init__(self) -> None:
        self._seen_urls: set[str] = set()
        self._seen_fingerprints: set[str] = set()
        self._seen_names: set[str] = set()

    def is_duplicate(
        self,
        lead: BusinessLead,
        profile_url: Optional[str] = None,
    ) -> bool:
        url_key = (profile_url or lead.source_url or "").strip().lower()
        if url_key and url_key in self._seen_urls:
            return True

        name_key = _normalize_name(lead.company_name)
        if name_key and name_key in self._seen_names:
            return True

        fp = fingerprint(lead)
        if fp in self._seen_fingerprints:
            return True

        return False

    def register(self, lead: BusinessLead, profile_url: Optional[str] = None) -> None:
        url_key = (profile_url or lead.source_url or "").strip().lower()
        if url_key:
            self._seen_urls.add(url_key)

        name_key = _normalize_name(lead.company_name)
        if name_key:
            self._seen_names.add(name_key)

        self._seen_fingerprints.add(fingerprint(lead))

    def has_seen_url(self, url: str) -> bool:
        return url.strip().lower() in self._seen_urls

    def register_url(self, url: str) -> None:
        url_key = url.strip().lower()
        if url_key:
            self._seen_urls.add(url_key)
