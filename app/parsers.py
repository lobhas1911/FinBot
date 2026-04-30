"""
Document Parsers
Handles PDF (with OCR fallback), HTML (with Playwright fallback), and Excel files.
Returns list of { "text": str, "page": int, "url": str, "doc_type": str }
"""

import io
import logging
import requests
import fitz  # PyMuPDF
import pandas as pd
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def parse_source(source: dict) -> list[dict]:
    """
    Main entry point. Routes to the correct parser based on URL/type.
    Returns list of page dicts: { text, page, url, doc_type }
    """
    url = source["url"]
    doc_type = source.get("type", "html")

    try:
        if doc_type == "pdf" or url.lower().endswith(".pdf"):
            return _parse_pdf(url)
        elif url.lower().endswith((".xlsx", ".xls")):
            return _parse_excel(url)
        else:
            return _parse_html(url)
    except Exception as e:
        logger.error(f"Failed to parse {url}: {e}")
        return []


# ---------------------------------------------------------------------------
# PDF Parser
# ---------------------------------------------------------------------------

def _parse_pdf(url: str) -> list[dict]:
    resp = requests.get(url, headers=HEADERS, timeout=30, stream=True)
    resp.raise_for_status()

    pdf_bytes = resp.content
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text").strip()

        # OCR fallback for image-based pages
        if len(text) < 50:
            text = _ocr_page(page)

        if text:
            pages.append({
                "text": text,
                "page": page_num + 1,
                "url": url,
                "doc_type": "pdf"
            })

    doc.close()
    logger.info(f"PDF parsed: {len(pages)} pages from {url}")
    return pages


def _ocr_page(page) -> str:
    """Render PDF page as image and run OCR."""
    try:
        import pytesseract
        from PIL import Image

        pix = page.get_pixmap(dpi=200)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        text = pytesseract.image_to_string(img)
        return text.strip()
    except Exception as e:
        logger.warning(f"OCR failed: {e}")
        return ""


# ---------------------------------------------------------------------------
# HTML Parser
# ---------------------------------------------------------------------------

def _parse_html(url: str) -> list[dict]:
    """Try requests+BeautifulSoup first, fall back to Playwright for JS pages."""
    text = _fetch_static_html(url)

    # If we got very little text, try Playwright
    if len(text) < 200:
        text = _fetch_js_html(url)

    if not text:
        return []

    return [{
        "text": text,
        "page": 1,
        "url": url,
        "doc_type": "html"
    }]


def _fetch_static_html(url: str) -> str:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Remove nav, footer, scripts, styles
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        # Prefer main content areas
        main = soup.find("main") or soup.find("article") or soup.find("div", {"id": "content"})
        target = main if main else soup.body
        text = target.get_text(separator="\n", strip=True) if target else ""
        return text
    except Exception as e:
        logger.warning(f"Static HTML fetch failed for {url}: {e}")
        return ""


def _fetch_js_html(url: str) -> str:
    """Use Playwright for JavaScript-rendered pages."""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=30000, wait_until="networkidle")
            content = page.content()
            browser.close()

        soup = BeautifulSoup(content, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        return text
    except Exception as e:
        logger.warning(f"Playwright fetch failed for {url}: {e}")
        return ""


# ---------------------------------------------------------------------------
# Excel Parser
# ---------------------------------------------------------------------------

def _parse_excel(url: str) -> list[dict]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        df_dict = pd.read_excel(io.BytesIO(resp.content), sheet_name=None)

        pages = []
        for sheet_name, df in df_dict.items():
            text = f"Sheet: {sheet_name}\n" + df.to_string(index=False)
            pages.append({
                "text": text,
                "page": 1,
                "url": url,
                "doc_type": "excel"
            })
        return pages
    except Exception as e:
        logger.error(f"Excel parse failed for {url}: {e}")
        return []
