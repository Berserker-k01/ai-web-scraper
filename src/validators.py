import re
from typing import Iterable, List, Optional
from urllib.parse import urlparse

import phonenumbers

# RFC-inspired email pattern with common TLD support
EMAIL_PATTERN = re.compile(
    r"(?<![\w.])"
    r"[a-zA-Z0-9](?:[a-zA-Z0-9._%+\-]*[a-zA-Z0-9])?"
    r"@"
    r"[a-zA-Z0-9](?:[a-zA-Z0-9\-]*[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9\-]*[a-zA-Z0-9])?)+"
    r"(?![\w.])"
)

PHONE_PATTERN = re.compile(
    r"(?:\+?\d{1,3}[\s\-.]?)?"
    r"(?:\(?\d{2,4}\)?[\s\-.]?)?"
    r"\d{2,4}[\s\-.]?\d{2,4}[\s\-.]?\d{2,4}(?:[\s\-.]?\d{1,4})?"
)

SOCIAL_PATTERNS = {
    "facebook": re.compile(r"https?://(?:www\.)?facebook\.com/[^\s\"'<>]+", re.I),
    "linkedin": re.compile(r"https?://(?:www\.)?linkedin\.com/[^\s\"'<>]+", re.I),
    "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/[^\s\"'<>]+", re.I),
    "whatsapp": re.compile(
        r"https?://(?:wa\.me|api\.whatsapp\.com)/[^\s\"'<>]+|"
        r"https?://(?:www\.)?whatsapp\.com/[^\s\"'<>]+",
        re.I,
    ),
}

JUNK_EMAIL_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".css", ".js", ".webp")
JUNK_EMAIL_LOCAL_PARTS = ("noreply", "no-reply", "donotreply", "example", "test", "sentry")


def is_valid_email(email: str) -> bool:
    email = email.strip().lower()
    if not email or len(email) > 254:
        return False
    if not EMAIL_PATTERN.fullmatch(email):
        return False
    if any(email.endswith(suffix) for suffix in JUNK_EMAIL_SUFFIXES):
        return False
    local = email.split("@")[0]
    if any(local.startswith(prefix) for prefix in JUNK_EMAIL_LOCAL_PARTS):
        return False
    return True


def extract_emails(text: str) -> List[str]:
    if not text:
        return []
    found = []
    for match in EMAIL_PATTERN.findall(text):
        email = match.strip().lower().rstrip(".,;)")
        if is_valid_email(email) and email not in found:
            found.append(email)
    return found


def normalize_phone(phone: str, default_region: str = "FR") -> str:
    phone = phone.strip()
    if not phone:
        return ""
    try:
        parsed = phonenumbers.parse(phone, default_region)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        pass
    digits = re.sub(r"[^\d+]", "", phone)
    return digits if len(re.sub(r"\D", "", digits)) >= 8 else ""


def extract_phones(text: str, default_region: str = "FR") -> List[str]:
    if not text:
        return []
    found = []
    for match in PHONE_PATTERN.findall(text):
        normalized = normalize_phone(match, default_region)
        if normalized and normalized not in found:
            found.append(normalized)
    return found


def extract_social_links(text: str) -> dict[str, str]:
    links = {}
    for platform, pattern in SOCIAL_PATTERNS.items():
        match = pattern.search(text or "")
        if match:
            links[platform] = match.group(0).rstrip(".,;)'\"")
    return links


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    if not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"


def pick_primary(values: Iterable[str]) -> str:
    for value in values:
        if value:
            return value
    return ""


def merge_unique(existing: List[str], new_items: Iterable[str]) -> List[str]:
    merged = list(existing)
    for item in new_items:
        item = (item or "").strip()
        if item and item not in merged:
            merged.append(item)
    return merged


def detect_country_region(country: str) -> str:
    mapping = {
        "france": "FR",
        "fr": "FR",
        "canada": "CA",
        "ca": "CA",
        "belgium": "BE",
        "belgique": "BE",
        "switzerland": "CH",
        "suisse": "CH",
        "morocco": "MA",
        "maroc": "MA",
        "senegal": "SN",
        "côte d'ivoire": "CI",
        "ivory coast": "CI",
        "cameroon": "CM",
        "cameroun": "CM",
        "united states": "US",
        "usa": "US",
        "united kingdom": "GB",
        "uk": "GB",
    }
    return mapping.get((country or "").strip().lower(), "FR")


def validate_lead_quality(lead: dict) -> List[str]:
    issues = []
    if not lead.get("company_name"):
        issues.append("missing company name")
    if not lead.get("phone") and not lead.get("email"):
        issues.append("no contact info")
    if lead.get("email") and not is_valid_email(lead["email"]):
        issues.append("invalid primary email")
    if lead.get("website") and not urlparse(lead["website"]).netloc:
        issues.append("invalid website URL")
    return issues
