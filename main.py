"""
Finance Analysis Chatbot — FastAPI Backend (yfinance edition)
"""

import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.finance_data import get_company_data, resolve_ticker, get_chart_data
from app.analysis import analyze
from app.config import LLM_PROVIDER, GROK_API_KEY

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

if not GROK_API_KEY:
    raise EnvironmentError("GROK_API_KEY is missing. Add it to your .env file.")

app = FastAPI(title="Finance Analysis Chatbot")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory="static"), name="static")

# In-memory session cache: ticker -> company_data
_session_cache: dict = {}
# Map resolved ticker back from original input for lookup
_ticker_map: dict = {}  # company_name_lower -> ticker


class ChatRequest(BaseModel):
    ticker: str
    question: str


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.get("/api/load/{company:path}")
def load_company(company: str):
    company = company.strip()
    if not company:
        raise HTTPException(400, "Company name is required")

    # Check if we already resolved this name
    cached_ticker = _ticker_map.get(company.lower())
    if cached_ticker and cached_ticker in _session_cache:
        data = _session_cache[cached_ticker]
        charts = get_chart_data(data)
        return _build_response(cached_ticker, data, charts)

    # Resolve ticker
    ticker = resolve_ticker(company)
    if not ticker:
        raise HTTPException(404, f"Could not find '{company}'. Try a more specific name (e.g. 'HDFC Bank', 'Tata Motors', 'Apple Inc').")

    # Fetch data
    if ticker not in _session_cache:
        logger.info(f"Fetching data for {ticker}...")
        try:
            data = get_company_data(ticker)
        except Exception as e:
            logger.error(f"Data fetch failed for {ticker}: {e}")
            raise HTTPException(500, f"Failed to fetch data for '{ticker}': {str(e)}")

        if not data["info"].get("name"):
            raise HTTPException(404, f"No data found for '{company}'.")
        _session_cache[ticker] = data
    else:
        data = _session_cache[ticker]

    _ticker_map[company.lower()] = ticker
    charts = get_chart_data(data)
    return _build_response(ticker, data, charts)


def _build_response(ticker: str, data: dict, charts: dict) -> dict:
    sources = []
    if data["income_statement"]:
        sources.append({"name": "Income Statement (Annual)", "type": "data", "status": "loaded", "url": None})
    if data["balance_sheet"]:
        sources.append({"name": "Balance Sheet (Annual)", "type": "data", "status": "loaded", "url": None})
    if data["cash_flow"]:
        sources.append({"name": "Cash Flow Statement (Annual)", "type": "data", "status": "loaded", "url": None})
    if data["ratios"]:
        sources.append({"name": "Key Ratios & Valuation Metrics", "type": "data", "status": "loaded", "url": None})
    if data["price_history"]:
        sources.append({"name": "Stock Price History (2Y)", "type": "data", "status": "loaded", "url": None})
    for link in data.get("source_links", []):
        sources.append({"name": link["name"], "type": link["type"], "status": "link", "url": link["url"]})
    for err in data["errors"]:
        sources.append({"name": err, "type": "error", "status": "failed", "url": None})

    return {
        "ticker": ticker,
        "name": data["info"].get("name", ticker),
        "info": data["info"],
        "ratios": data["ratios"],
        "sources": sources,
        "charts": charts
    }


@app.get("/api/analyze/{ticker:path}")
def full_analysis(ticker: str):
    ticker = ticker.strip()
    # Try exact match first, then uppercase
    data = _session_cache.get(ticker) or _session_cache.get(ticker.upper())
    if not data:
        # Try resolving from ticker map
        mapped = _ticker_map.get(ticker.lower())
        if mapped:
            data = _session_cache.get(mapped)
    if not data:
        raise HTTPException(404, f"No data loaded for '{ticker}'. Load the company first.")

    try:
        analysis_text = analyze(data)
        return {"analysis": analysis_text}
    except Exception as e:
        logger.error(f"Analysis failed for {ticker}: {e}")
        raise HTTPException(500, f"Analysis failed: {str(e)}")


@app.post("/api/chat")
def chat(req: ChatRequest):
    ticker = req.ticker.strip()
    question = req.question.strip()

    if not question:
        raise HTTPException(400, "Question is required")

    # Try exact match, then uppercase, then ticker map
    data = _session_cache.get(ticker) or _session_cache.get(ticker.upper())
    if not data:
        mapped = _ticker_map.get(ticker.lower())
        if mapped:
            data = _session_cache.get(mapped)
    if not data:
        raise HTTPException(404, f"No data loaded for '{ticker}'. Load the company first.")

    try:
        answer = analyze(data, question=question)
        return {"answer": answer}
    except Exception as e:
        logger.error(f"Chat failed for {ticker}: {e}")
        raise HTTPException(500, f"Chat failed: {str(e)}")


@app.delete("/api/session/{ticker:path}")
def clear_session(ticker: str):
    ticker = ticker.strip()
    _session_cache.pop(ticker, None)
    _session_cache.pop(ticker.upper(), None)
    return {"message": f"Session cleared for {ticker}"}
