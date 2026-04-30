"""
Source Discovery Layer
Finds financial document URLs for a given company name.
Supports: Indian companies (Screener.in, BSE, NSE) and US companies (SEC EDGAR).
Falls back to DuckDuckGo search when structured sources fail.
"""

import re
import logging
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from app.config import SERPAPI_KEY, MAX_DOCS_PER_SESSION

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def discover_sources(company_name: str) -> list[dict]:
    """
    Returns a deduplicated list of source dicts:
      { "url": str, "title": str, "type": "pdf"|"html", "source": str }
    """
    results = []
    seen_urls = set()

    def add(items: list[dict]):
        for item in items:
            url = item.get("url", "").strip()
            if url and url not in seen_urls:
                seen_urls.add(url)
                results.append(item)

    # 1. Screener.in (Indian companies)
    try:
        add(_screener(company_name))
    except Exception as e:
        logger.warning(f"Screener.in failed: {e}")

    # 2. SEC EDGAR (US companies)
    try:
        add(_sec_edgar(company_name))
    except Exception as e:
        logger.warning(f"SEC EDGAR failed: {e}")

    # 3. BSE India
    try:
        add(_bse_search(company_name))
    except Exception as e:
        logger.warning(f"BSE search failed: {e}")

    # 4. DuckDuckGo fallback (always runs to fill gaps)
    try:
        add(_ddg_search(company_name))
    except Exception as e:
        logger.warning(f"DuckDuckGo search failed: {e}")

    logger.info(f"Discovered {len(results)} sources for '{company_name}'")
    return results[:MAX_DOCS_PER_SESSION]


# ---------------------------------------------------------------------------
# Screener.in
# ---------------------------------------------------------------------------

def _screener(company_name: str) -> list[dict]:
    """Scrape Screener.in for the company's financial page."""
    query = company_name.strip().replace(" ", "+")
    search_url = f"https://www.screener.in/api/company/search/?q={query}&v=3&fts=1"

    resp = requests.get(search_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    results = []
    if data and isinstance(data, list):
        top = data[0]
        slug = top.get("url", "")
        if slug:
            company_url = f"https://www.screener.in{slug}"
            results.append({
                "url": company_url,
                "title": f"{top.get('name', company_name)} — Screener.in",
                "type": "html",
                "source": "screener.in"
            })
            # Also grab the consolidated financials page
            results.append({
                "url": company_url + "#profit-loss",
                "title": f"{top.get('name', company_name)} P&L — Screener.in",
                "type": "html",
                "source": "screener.in"
            })

    return results


# ---------------------------------------------------------------------------
# SEC EDGAR (US companies)
# ---------------------------------------------------------------------------

def _sec_edgar(company_name: str) -> list[dict]:
    """Query SEC EDGAR full-text search for 10-K and 10-Q filings."""
    search_url = "https://efts.sec.gov/LATEST/search-index?q=%22{}%22&dateRange=custom&startdt=2022-01-01&forms=10-K,10-Q".format(
        requests.utils.quote(company_name)
    )
    resp = requests.get(search_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    results = []
    hits = data.get("hits", {}).get("hits", [])
    for hit in hits[:4]:
        src = hit.get("_source", {})
        file_date = src.get("file_date", "")
        form_type = src.get("form_type", "filing")
        entity = src.get("entity_name", company_name)
        accession = src.get("accession_no", "").replace("-", "")
        cik = str(src.get("entity_id", "")).zfill(10)

        if accession and cik:
            filing_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/{src.get('file_name', '')}"
            results.append({
                "url": filing_url,
                "title": f"{entity} {form_type} ({file_date})",
                "type": "html",
                "source": "sec.gov"
            })

    return results


# ---------------------------------------------------------------------------
# BSE India
# ---------------------------------------------------------------------------

def _bse_search(company_name: str) -> list[dict]:
    """Search BSE India for annual report PDFs."""
    query = company_name.strip().replace(" ", "%20")
    url = f"https://api.bseindia.com/BseIndiaAPI/api/AnnualReport/w?scripcode=&companyname={query}&industry=&segment=Equity"

    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    results = []
    for item in data.get("Table", [])[:3]:
        pdf_url = item.get("PDFURL", "")
        company = item.get("COMPANYNAME", company_name)
        year = item.get("YEAR", "")
        if pdf_url:
            results.append({
                "url": pdf_url,
                "title": f"{company} Annual Report {year}",
                "type": "pdf",
                "source": "bseindia.com"
            })

    return results


# ---------------------------------------------------------------------------
# DuckDuckGo fallback
# ---------------------------------------------------------------------------

def _ddg_search(company_name: str) -> list[dict]:
    """Use DuckDuckGo to find annual reports and financial statements."""
    queries = [
        f"{company_name} annual report 2024 filetype:pdf",
        f"{company_name} balance sheet income statement 2024",
        f"{company_name} investor relations annual report",
    ]

    results = []
    seen = set()

    with DDGS() as ddgs:
        for q in queries:
            try:
                hits = list(ddgs.text(q, max_results=4))
                for h in hits:
                    url = h.get("href", "")
                    title = h.get("title", "")
                    if url and url not in seen:
                        seen.add(url)
                        doc_type = "pdf" if url.lower().endswith(".pdf") else "html"
                        results.append({
                            "url": url,
                            "title": title,
                            "type": doc_type,
                            "source": "duckduckgo"
                        })
            except Exception as e:
                logger.warning(f"DDG query failed for '{q}': {e}")

    return results
