import os

# LLM — DeepSeek via LiteLLM
# https://docs.litellm.ai/docs/providers/deepseek
LLM_MODEL = "deepseek/deepseek-chat"
API_TOKEN = os.getenv("DEEPSEEK_API_KEY")

# Crawl settings
REQUEST_DELAY_SECONDS = 2
MAX_RESULT_PAGES = 100
OUTPUT_DIR = "output"
HEADLESS = True

# Website enrichment — paths to probe for extra contacts
WEBSITE_PATHS = [
    "",
    "/contact",
    "/contact-us",
    "/contactez-nous",
    "/nous-contacter",
    "/about",
    "/about-us",
    "/a-propos",
    "/qui-sommes-nous",
    "/mentions-legales",
    "/legal",
    "/legal-notice",
    "/privacy",
    "/privacy-policy",
    "/impressum",
]

LISTING_INSTRUCTIONS = (
    "You are analyzing a business directory search-results or category page "
    "(GoAfricaOnline, Pages Jaunes, Kompass, Europages, YellowPages, etc.).\n"
    "1. Identify every real company listing. IGNORE advertisements, sponsored results, "
    "navigation links, filters, and pagination controls themselves.\n"
    "2. For each company, extract the profile_url (absolute URL to the company detail page) "
    "and company_name if visible.\n"
    "3. Find the next_page_url: the absolute URL to the next page of results. "
    "Leave empty if this is the last page.\n"
    "Adapt to the HTML structure of the site — field labels and layouts vary."
)

PROFILE_INSTRUCTIONS = (
    "Extract complete B2B lead data from this company profile/detail page.\n"
    "Fields: company_name, industry, description, address, city, country, phone, "
    "secondary_phones (list), email, emails (list), website, facebook, linkedin, "
    "instagram, whatsapp, latitude, longitude.\n"
    "Use empty strings for missing scalar fields and empty lists for missing lists.\n"
    "Extract emails and phones even from free text. Ignore ads."
)

WEBSITE_INSTRUCTIONS = (
    "Extract contact information from this company website page.\n"
    "Fields: phone, secondary_phones, email, emails, website, facebook, linkedin, "
    "instagram, whatsapp.\n"
    "Focus on footer, contact sections, and legal mentions. Use empty values when absent."
)
