import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from urllib.parse import urljoin, urlparse

from crawl4ai import AsyncWebCrawler

from config import (
    LISTING_INSTRUCTIONS,
    MAX_RESULT_PAGES,
    OUTPUT_DIR,
    PROFILE_INSTRUCTIONS,
    REQUEST_DELAY_SECONDS,
)
from models.business import BusinessLead, ListingItem, ListingPageResult
from src.dedup import Deduplicator
from src.enrichment import enrich_from_website
from src.exporters import export_all
from src.progress import ProgressTracker
from src.scraper import (
    absolutize_url,
    extract_with_llm,
    get_browser_config,
    get_llm_strategy,
    same_domain,
)
from src.validators import (
    detect_country_region,
    is_valid_email,
    merge_unique,
    normalize_phone,
    normalize_url,
    pick_primary,
    validate_lead_quality,
)


class LeadScraper:
    def __init__(self, progress: Optional[ProgressTracker] = None) -> None:
        self.progress = progress or ProgressTracker()
        self._leads: List[BusinessLead] = []
        self._dedup = Deduplicator()
        self._output_dir: Optional[Path] = None

    @property
    def leads(self) -> List[BusinessLead]:
        return list(self._leads)

    def _count_emails(self) -> int:
        total = 0
        for lead in self._leads:
            if lead.email:
                total += 1
            total += len(lead.emails)
        return total

    def _count_phones(self) -> int:
        total = 0
        for lead in self._leads:
            if lead.phone:
                total += 1
            total += len(lead.secondary_phones)
        return total

    def _update_stats(self, message: str, current_url: str = "") -> None:
        kwargs = {
            "message": message,
            "companies_found": len(self._leads),
            "emails_found": self._count_emails(),
            "phones_found": self._count_phones(),
        }
        if current_url:
            kwargs["current_url"] = current_url
        self.progress.update(**kwargs)

    def _save_progressive(self) -> None:
        if self._output_dir:
            export_all(self._leads, self._output_dir)

    def _normalize_lead(self, data: dict, source_url: str) -> BusinessLead:
        region = detect_country_region(data.get("country", ""))
        phones_raw = merge_unique(
            [data.get("phone", "")],
            data.get("secondary_phones", []),
        )
        phones = [normalize_phone(p, region) for p in phones_raw]
        phones = [p for p in phones if p]
        phones = list(dict.fromkeys(phones))

        emails_raw = merge_unique(
            [data.get("email", "")],
            data.get("emails", []),
        )
        emails = [e.strip().lower() for e in emails_raw if is_valid_email(e)]
        emails = list(dict.fromkeys(emails))

        company_name = (data.get("company_name") or data.get("name") or "").strip()
        if not company_name:
            company_name = "Unknown"

        return BusinessLead(
            company_name=company_name,
            industry=(data.get("industry") or "").strip(),
            description=(data.get("description") or "").strip(),
            address=(data.get("address") or "").strip(),
            city=(data.get("city") or "").strip(),
            country=(data.get("country") or "").strip(),
            phone=pick_primary(phones),
            secondary_phones=[p for p in phones if p != pick_primary(phones)],
            email=pick_primary(emails),
            emails=[e for e in emails if e != pick_primary(emails)],
            website=normalize_url(data.get("website", "")),
            facebook=(data.get("facebook") or "").strip(),
            linkedin=(data.get("linkedin") or "").strip(),
            instagram=(data.get("instagram") or "").strip(),
            whatsapp=(data.get("whatsapp") or "").strip(),
            latitude=str(data.get("latitude") or "").strip(),
            longitude=str(data.get("longitude") or "").strip(),
            source_url=source_url,
        )

    async def _extract_listing_page(
        self,
        crawler: AsyncWebCrawler,
        url: str,
        session_id: str,
    ) -> ListingPageResult:
        strategy = get_llm_strategy(LISTING_INSTRUCTIONS, ListingPageResult)
        data = await extract_with_llm(crawler, url, session_id, strategy)

        if not data:
            return ListingPageResult()

        companies = []
        for item in data.get("companies", []):
            if not isinstance(item, dict):
                continue
            profile_url = absolutize_url(url, item.get("profile_url", ""))
            if not profile_url:
                continue
            companies.append(
                ListingItem(
                    profile_url=profile_url,
                    company_name=(item.get("company_name") or "").strip(),
                )
            )

        next_page = absolutize_url(url, data.get("next_page_url", ""))
        if next_page and not same_domain(url, next_page):
            next_page = ""

        return ListingPageResult(companies=companies, next_page_url=next_page)

    async def _extract_profile(
        self,
        crawler: AsyncWebCrawler,
        profile_url: str,
        session_id: str,
        fallback_name: str = "",
    ) -> Optional[BusinessLead]:
        strategy = get_llm_strategy(PROFILE_INSTRUCTIONS, BusinessLead)
        data = await extract_with_llm(crawler, profile_url, session_id, strategy)
        if not data:
            return None

        if fallback_name and not data.get("company_name"):
            data["company_name"] = fallback_name

        lead = self._normalize_lead(data, profile_url)

        if lead.website:
            self._update_stats(
                f"Enrichissement du site : {lead.company_name}",
                lead.website,
            )
            lead = await enrich_from_website(crawler, lead, session_id)

        return lead

    async def run(
        self,
        start_url: str,
        output_dir: Optional[str] = None,
        max_pages: Optional[int] = None,
    ) -> List[BusinessLead]:
        page_limit = max_pages if max_pages is not None else MAX_RESULT_PAGES
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._output_dir = Path(output_dir or OUTPUT_DIR) / timestamp
        self._output_dir.mkdir(parents=True, exist_ok=True)

        self.progress.reset(start_url, str(self._output_dir))
        session_id = f"lead_scraper_{timestamp}"
        browser_config = get_browser_config()

        current_url = start_url.strip()
        page_num = 0
        visited_listing_pages: set[str] = set()
        profiles_visited = 0
        duplicates_skipped = 0

        try:
            async with AsyncWebCrawler(config=browser_config) as crawler:
                while current_url and page_num < page_limit:
                    if current_url in visited_listing_pages:
                        break
                    visited_listing_pages.add(current_url)
                    page_num += 1

                    self.progress.update(
                        current_page=page_num,
                        current_url=current_url,
                        message=f"Analyse de la page de résultats {page_num}...",
                    )

                    listing = await self._extract_listing_page(
                        crawler, current_url, session_id
                    )

                    if not listing.companies:
                        self.progress.add_issue(
                            f"Aucune entreprise sur la page {page_num} — fin du crawl."
                        )
                        break

                    for item in listing.companies:
                        profile_url = item.profile_url
                        profiles_visited += 1
                        self.progress.update(
                            profiles_visited=profiles_visited,
                            message=f"Fiche : {item.company_name or profile_url}",
                            current_url=profile_url,
                        )

                        if self._dedup.has_seen_url(profile_url):
                            duplicates_skipped += 1
                            self.progress.update(duplicates_skipped=duplicates_skipped)
                            continue

                        self._dedup.register_url(profile_url)

                        lead = await self._extract_profile(
                            crawler,
                            profile_url,
                            session_id,
                            fallback_name=item.company_name,
                        )
                        if not lead:
                            self.progress.add_issue(f"Échec extraction : {profile_url}")
                            continue

                        if self._dedup.is_duplicate(lead, profile_url):
                            duplicates_skipped += 1
                            self.progress.update(
                                duplicates_skipped=duplicates_skipped,
                                message=f"Doublon ignoré : {lead.company_name}",
                            )
                            continue

                        issues = validate_lead_quality(lead.model_dump())
                        for issue in issues:
                            self.progress.add_issue(
                                f"{lead.company_name}: {issue}"
                            )

                        self._dedup.register(lead, profile_url)
                        self._leads.append(lead)
                        self._save_progressive()
                        self.progress.add_recent_lead(lead.to_export_row())
                        self._update_stats(
                            f"✓ {lead.company_name} — {len(self._leads)} entreprises",
                            profile_url,
                        )

                        await asyncio.sleep(REQUEST_DELAY_SECONDS)

                    next_url = listing.next_page_url
                    if not next_url or next_url == current_url:
                        break
                    current_url = next_url
                    await asyncio.sleep(REQUEST_DELAY_SECONDS)

            export_files = export_all(self._leads, self._output_dir)
            self.progress.complete(
                export_files,
                message=f"Terminé — {len(self._leads)} entreprises exportées.",
            )
        except Exception as exc:
            self._save_progressive()
            self.progress.fail(str(exc))
            raise

        return self._leads
