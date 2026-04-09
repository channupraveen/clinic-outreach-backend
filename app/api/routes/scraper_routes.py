"""
Scrape email addresses from clinic websites.
V2 — Much more aggressive: checks multiple pages, decodes obfuscated emails,
parses mailto: links, handles JS-rendered content patterns.
"""
import re
import asyncio
import html as html_lib
from urllib.parse import urljoin, urlparse
from typing import List, Optional, Set
from pydantic import BaseModel
import httpx

from fastapi import APIRouter

router = APIRouter(prefix="/scraper", tags=["Scraper"])


class ScrapeRequest(BaseModel):
    urls: List[str]


class ScrapeResult(BaseModel):
    url: str
    emails: List[str]
    pages_checked: int = 0
    error: Optional[str] = None


class ScrapeResponse(BaseModel):
    results: List[ScrapeResult]


# ---- Junk filters ----
IGNORE_DOMAINS = {
    "example.com", "yoursite.com", "yourdomain.com", "sentry.io",
    "wixpress.com", "googleapis.com", "w3.org", "schema.org",
    "wordpress.org", "wordpress.com", "gravatar.com", "wp.com",
    "google.com", "gstatic.com", "facebook.com", "twitter.com",
    "instagram.com", "youtube.com", "linkedin.com", "yelp.com",
    "cloudflare.com", "jsdelivr.net", "bootstrapcdn.com",
    "fontawesome.com", "jquery.com", "unpkg.com", "cdnjs.com",
    "squarespace.com", "squarespace-cdn.com", "sentry-next.wixpress.com",
    "weebly.com", "godaddy.com", "mailchimp.com",
}

IGNORE_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico',
    '.css', '.js', '.woff', '.woff2', '.ttf', '.eot', '.map',
    '.pdf', '.zip', '.mp4', '.mp3',
}

IGNORE_PREFIXES = {'noreply@', 'no-reply@', 'mailer-daemon@', 'postmaster@'}

# ---- Regex patterns ----
EMAIL_REGEX = re.compile(
    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,7}',
    re.IGNORECASE
)

# Matches mailto: links (often have the best emails)
MAILTO_REGEX = re.compile(
    r'mailto:([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,7})',
    re.IGNORECASE
)

# Matches href="mailto:..." with possible URL encoding
MAILTO_ENCODED_REGEX = re.compile(
    r'mailto:([a-zA-Z0-9._%+\-]+%40[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,7})',
    re.IGNORECASE
)

# Matches emails written as "info [at] domain [dot] com"
AT_DOT_REGEX = re.compile(
    r'([a-zA-Z0-9._%+\-]+)\s*[\[\(]\s*at\s*[\]\)]\s*([a-zA-Z0-9.\-]+)\s*[\[\(]\s*dot\s*[\]\)]\s*([a-zA-Z]{2,7})',
    re.IGNORECASE
)

# Common contact page URL patterns to try
CONTACT_PATHS = [
    '/contact',
    '/contact-us',
    '/contact-us/',
    '/about',
    '/about-us',
    '/about/',
    '/our-team',
    '/team',
    '/staff',
    '/location',
    '/locations',
]


def is_valid_email(email: str) -> bool:
    """Check if email looks like a real clinic email, not junk."""
    email = email.lower().strip()

    # Extension check
    for ext in IGNORE_EXTENSIONS:
        if email.endswith(ext):
            return False

    # Domain check
    if '@' not in email:
        return False
    domain = email.split('@')[1]
    for ign in IGNORE_DOMAINS:
        if domain == ign or domain.endswith('.' + ign):
            return False

    # Prefix check
    for prefix in IGNORE_PREFIXES:
        if email.startswith(prefix):
            return False

    # Must have at least 2 chars before @
    local = email.split('@')[0]
    if len(local) < 2:
        return False

    # TLD must be 2-7 chars
    tld = domain.split('.')[-1]
    if len(tld) < 2 or len(tld) > 7:
        return False

    return True


def extract_emails_from_html(html_content: str) -> List[str]:
    """Extract emails using multiple strategies."""
    found: Set[str] = set()

    # 1) HTML-decode the content first (handles &amp; &#64; etc.)
    decoded = html_lib.unescape(html_content)

    # 2) mailto: links (highest quality — intentionally placed)
    for match in MAILTO_REGEX.findall(decoded):
        found.add(match.lower().strip())

    # 3) URL-encoded mailto: (e.g., %40 instead of @)
    for match in MAILTO_ENCODED_REGEX.findall(decoded):
        email = match.replace('%40', '@').lower().strip()
        found.add(email)

    # 4) Standard regex on decoded HTML
    for match in EMAIL_REGEX.findall(decoded):
        found.add(match.lower().strip())

    # 5) Also scan the raw HTML (before decode) for any differences
    for match in EMAIL_REGEX.findall(html_content):
        found.add(match.lower().strip())

    # 6) [at] / [dot] obfuscation
    for m in AT_DOT_REGEX.finditer(decoded):
        email = f"{m.group(1)}@{m.group(2)}.{m.group(3)}".lower()
        found.add(email)

    # 7) Look for JSON-LD structured data (schema.org)
    # Pattern: "email":"info@clinic.com"
    json_email = re.findall(r'"email"\s*:\s*"([^"]+@[^"]+)"', decoded, re.IGNORECASE)
    for e in json_email:
        found.add(e.lower().strip())

    # 8) Look for data attributes with emails
    data_email = re.findall(r'data-email=["\']([^"\']+@[^"\']+)["\']', decoded, re.IGNORECASE)
    for e in data_email:
        found.add(e.lower().strip())

    # 9) Look for reversed emails (anti-spam trick: moc.cinilc@ofni)
    # We skip this — too many false positives

    # Filter
    valid = [e for e in found if is_valid_email(e)]

    # Sort: prefer info@, office@, contact@ etc. — these are the outreach targets
    def email_priority(e: str) -> int:
        local = e.split('@')[0]
        priority_prefixes = ['info', 'contact', 'office', 'hello', 'admin', 'reception', 'frontdesk', 'appointments']
        for i, prefix in enumerate(priority_prefixes):
            if local == prefix:
                return i
            if local.startswith(prefix):
                return i + 100
        return 999

    valid.sort(key=email_priority)
    return valid[:5]


def find_contact_links(html_content: str, base_url: str) -> List[str]:
    """Find links to contact/about pages in the HTML."""
    links: List[str] = []
    # Find all href values
    href_pattern = re.compile(r'href=["\']([^"\']*)["\']', re.IGNORECASE)
    for href in href_pattern.findall(html_content):
        href_lower = href.lower()
        if any(kw in href_lower for kw in ['contact', 'about', 'team', 'staff', 'location']):
            full_url = urljoin(base_url, href)
            # Only follow links on the same domain
            if urlparse(full_url).netloc == urlparse(base_url).netloc:
                links.append(full_url)
    return list(set(links))[:5]  # max 5 internal links


async def fetch_page(client: httpx.AsyncClient, url: str) -> Optional[str]:
    """Fetch a single page, return HTML or None."""
    try:
        resp = await client.get(url, follow_redirects=True, timeout=12.0)
        if resp.status_code == 200 and 'text/html' in resp.headers.get('content-type', ''):
            return resp.text
    except Exception:
        pass
    return None


async def fetch_and_extract(client: httpx.AsyncClient, url: str) -> ScrapeResult:
    """Fetch URL + contact pages and extract emails."""
    # Normalize URL
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    url = url.rstrip('/')

    pages_checked = 0
    all_emails: Set[str] = set()

    try:
        # ---- Step 1: Homepage ----
        homepage_html = await fetch_page(client, url)
        if homepage_html:
            pages_checked += 1
            emails = extract_emails_from_html(homepage_html)
            all_emails.update(emails)

            # ---- Step 2: Find contact links from homepage ----
            if len(all_emails) == 0:
                contact_links = find_contact_links(homepage_html, url)
                for link in contact_links[:3]:
                    page_html = await fetch_page(client, link)
                    if page_html:
                        pages_checked += 1
                        emails = extract_emails_from_html(page_html)
                        all_emails.update(emails)
                        if all_emails:
                            break

        # ---- Step 3: Try common contact paths if still no emails ----
        if len(all_emails) == 0:
            for path in CONTACT_PATHS:
                contact_url = url + path
                page_html = await fetch_page(client, contact_url)
                if page_html:
                    pages_checked += 1
                    emails = extract_emails_from_html(page_html)
                    all_emails.update(emails)
                    if all_emails:
                        break

        # ---- Step 4: Try www. variant if no results ----
        if len(all_emails) == 0 and 'www.' not in url:
            parsed = urlparse(url)
            www_url = f"{parsed.scheme}://www.{parsed.netloc}{parsed.path}"
            page_html = await fetch_page(client, www_url)
            if page_html:
                pages_checked += 1
                emails = extract_emails_from_html(page_html)
                all_emails.update(emails)

        # Filter valid and sort
        valid = [e for e in all_emails if is_valid_email(e)]

        def email_priority(e: str) -> int:
            local = e.split('@')[0]
            for i, prefix in enumerate(['info', 'contact', 'office', 'hello', 'admin', 'reception']):
                if local == prefix:
                    return i
            return 999

        valid.sort(key=email_priority)

        return ScrapeResult(url=url, emails=valid[:5], pages_checked=pages_checked)

    except Exception as e:
        return ScrapeResult(url=url, emails=[], pages_checked=pages_checked, error=str(e)[:120])


@router.post("/extract-emails", response_model=ScrapeResponse)
async def extract_emails_endpoint(payload: ScrapeRequest):
    """
    Given a list of website URLs, fetch each and extract email addresses.
    V2: checks homepage + contact pages + common paths.
    Max 20 URLs per request.
    """
    urls = payload.urls[:20]

    async with httpx.AsyncClient(
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
        verify=False,
        timeout=15.0,
    ) as client:
        # Use semaphore to limit concurrency (avoid hammering)
        sem = asyncio.Semaphore(5)

        async def throttled(url: str):
            async with sem:
                return await fetch_and_extract(client, url)

        tasks = [throttled(url) for url in urls]
        results = await asyncio.gather(*tasks)

    return ScrapeResponse(results=list(results))
