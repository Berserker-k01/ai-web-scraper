import json
from typing import List, Optional, Type
from urllib.parse import urljoin, urlparse

from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CacheMode,
    CrawlerRunConfig,
    LLMExtractionStrategy,
)
from pydantic import BaseModel

from config import API_TOKEN, HEADLESS, LLM_MODEL


def get_browser_config() -> BrowserConfig:
    return BrowserConfig(
        browser_type="chromium",
        headless=HEADLESS,
        verbose=False,
    )


def get_llm_strategy(
    llm_instructions: str,
    output_format: Type[BaseModel],
) -> LLMExtractionStrategy:
    return LLMExtractionStrategy(
        provider=LLM_MODEL,
        api_token=API_TOKEN,
        schema=output_format.model_json_schema(),
        extraction_type="schema",
        instruction=llm_instructions,
        input_format="markdown",
        verbose=False,
    )


def _parse_llm_result(raw: str) -> list | dict | None:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _unwrap_items(data) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    return []


def _first_valid_item(items: list) -> Optional[dict]:
    for item in items:
        if isinstance(item, dict) and not item.get("error"):
            return item
    return None


async def fetch_page_markdown(
    crawler: AsyncWebCrawler,
    url: str,
    session_id: str,
) -> tuple[bool, str, str]:
    result = await crawler.arun(
        url=url,
        config=CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            session_id=session_id,
        ),
    )
    if not result.success:
        return False, "", result.error_message or "Fetch failed"

    content = result.markdown or result.cleaned_html or ""
    return True, content, ""


async def extract_with_llm(
    crawler: AsyncWebCrawler,
    url: str,
    session_id: str,
    llm_strategy: LLMExtractionStrategy,
) -> Optional[dict]:
    result = await crawler.arun(
        url=url,
        config=CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            extraction_strategy=llm_strategy,
            session_id=session_id,
        ),
    )
    if not result.success or not result.extracted_content:
        return None

    data = _parse_llm_result(result.extracted_content)
    if data is None:
        return None

    if isinstance(data, dict):
        if "companies" in data:
            return data
        return data

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("companies") is not None:
                return item
        return _first_valid_item(data)

    return None


def absolutize_url(base_url: str, link: str) -> str:
    link = (link or "").strip()
    if not link:
        return ""
    return urljoin(base_url, link)


def same_domain(url_a: str, url_b: str) -> bool:
    return urlparse(url_a).netloc.lower() == urlparse(url_b).netloc.lower()
