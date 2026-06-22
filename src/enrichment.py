from urllib.parse import urljoin, urlparse

from crawl4ai import AsyncWebCrawler

from config import WEBSITE_PATHS
from models.business import BusinessLead, ContactEnrichment
from src.scraper import extract_with_llm, fetch_page_markdown, get_llm_strategy
from src.validators import (
    detect_country_region,
    extract_emails,
    extract_phones,
    extract_social_links,
    is_valid_email,
    merge_unique,
    normalize_phone,
    normalize_url,
    pick_primary,
)
from config import WEBSITE_INSTRUCTIONS


async def enrich_from_website(
    crawler: AsyncWebCrawler,
    lead: BusinessLead,
    session_id: str,
) -> BusinessLead:
    website = normalize_url(lead.website)
    if not website:
        return lead

    region = detect_country_region(lead.country)
    collected_emails: list[str] = []
    collected_phones: list[str] = []
    social = {
        "facebook": lead.facebook,
        "linkedin": lead.linkedin,
        "instagram": lead.instagram,
        "whatsapp": lead.whatsapp,
    }

    llm_strategy = get_llm_strategy(WEBSITE_INSTRUCTIONS, ContactEnrichment)
    parsed = urlparse(website)
    base = f"{parsed.scheme}://{parsed.netloc}"

    for path in WEBSITE_PATHS:
        page_url = base if not path else urljoin(base + "/", path.lstrip("/"))
        ok, content, _ = await fetch_page_markdown(crawler, page_url, session_id)
        if not ok or not content:
            continue

        collected_emails = merge_unique(collected_emails, extract_emails(content))
        collected_phones = merge_unique(
            collected_phones,
            extract_phones(content, region),
        )

        page_social = extract_social_links(content)
        for key, value in page_social.items():
            if value and not social.get(key):
                social[key] = value

        llm_data = await extract_with_llm(crawler, page_url, session_id, llm_strategy)
        if llm_data:
            collected_emails = merge_unique(
                collected_emails,
                [llm_data.get("email", "")],
                llm_data.get("emails", []),
            )
            collected_phones = merge_unique(
                collected_phones,
                [llm_data.get("phone", "")],
                llm_data.get("secondary_phones", []),
            )
            for key in social:
                if llm_data.get(key) and not social[key]:
                    social[key] = llm_data[key]

    if lead.email:
        collected_emails = merge_unique([lead.email], collected_emails)
    if lead.emails:
        collected_emails = merge_unique(collected_emails, lead.emails)
    collected_emails = [e for e in collected_emails if is_valid_email(e)]

    if lead.phone:
        collected_phones = merge_unique([lead.phone], collected_phones)
    if lead.secondary_phones:
        collected_phones = merge_unique(collected_phones, lead.secondary_phones)
    collected_phones = [
        normalize_phone(p, region) for p in collected_phones if normalize_phone(p, region)
    ]
    collected_phones = list(dict.fromkeys(collected_phones))

    lead.email = pick_primary(collected_emails)
    lead.emails = [e for e in collected_emails if e != lead.email]
    lead.phone = pick_primary(collected_phones)
    lead.secondary_phones = [p for p in collected_phones if p != lead.phone]
    lead.website = website
    lead.facebook = social["facebook"] or lead.facebook
    lead.linkedin = social["linkedin"] or lead.linkedin
    lead.instagram = social["instagram"] or lead.instagram
    lead.whatsapp = social["whatsapp"] or lead.whatsapp

    return lead
