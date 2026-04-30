"""
Finance Data Layer
Fetches structured financial data from yfinance for any ticker/company.
"""

import logging
import yfinance as yf
import pandas as pd

logger = logging.getLogger(__name__)


def get_company_data(ticker: str) -> dict:
    stock = yf.Ticker(ticker)
    data = {
        "ticker": ticker.upper(),
        "info": {},
        "income_statement": {},
        "balance_sheet": {},
        "cash_flow": {},
        "ratios": {},
        "price_history": [],
        "source_links": [],
        "errors": []
    }

    # Info & ratios
    try:
        info = stock.info
        data["info"] = {
            "name": info.get("longName", ticker),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "country": info.get("country", "N/A"),
            "currency": info.get("currency", "USD"),
            "market_cap": info.get("marketCap"),
            "employees": info.get("fullTimeEmployees"),
            "description": info.get("longBusinessSummary", "")[:500],
            "website": info.get("website", ""),
            "exchange": info.get("exchange", ""),
        }
        data["ratios"] = {
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "pb_ratio": info.get("priceToBook"),
            "ps_ratio": info.get("priceToSalesTrailing12Months"),
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "quick_ratio": info.get("quickRatio"),
            "roe": info.get("returnOnEquity"),
            "roa": info.get("returnOnAssets"),
            "profit_margin": info.get("profitMargins"),
            "operating_margin": info.get("operatingMargins"),
            "gross_margin": info.get("grossMargins"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "dividend_yield": info.get("dividendYield"),
            "beta": info.get("beta"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
            "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
        }
        exchange = info.get("exchange", "")
        symbol_clean = ticker.replace(".NS", "").replace(".BO", "")
        data["source_links"] = _build_source_links(ticker, symbol_clean, exchange, info)
    except Exception as e:
        data["errors"].append(f"Info fetch failed: {e}")
        logger.warning(f"Info fetch failed for {ticker}: {e}")

    # Income Statement
    try:
        inc = stock.financials
        if inc is not None and not inc.empty:
            data["income_statement"] = _df_to_dict(inc)
    except Exception as e:
        data["errors"].append(f"Income statement failed: {e}")

    # Balance Sheet
    try:
        bs = stock.balance_sheet
        if bs is not None and not bs.empty:
            data["balance_sheet"] = _df_to_dict(bs)
    except Exception as e:
        data["errors"].append(f"Balance sheet failed: {e}")

    # Cash Flow
    try:
        cf = stock.cashflow
        if cf is not None and not cf.empty:
            data["cash_flow"] = _df_to_dict(cf)
    except Exception as e:
        data["errors"].append(f"Cash flow failed: {e}")

    # Price history (2 years, monthly)
    try:
        hist = stock.history(period="2y", interval="1mo")
        if not hist.empty:
            data["price_history"] = [
                {
                    "date": str(idx.date()),
                    "close": round(float(row["Close"]), 2),
                    "volume": int(row["Volume"])
                }
                for idx, row in hist.iterrows()
            ]
    except Exception as e:
        data["errors"].append(f"Price history failed: {e}")

    return data


def _build_source_links(ticker: str, symbol_clean: str, exchange: str, info: dict) -> list[dict]:
    links = []
    yf_symbol = ticker.replace(":", "-")

    links.append({"name": "Yahoo Finance — Financials", "url": f"https://finance.yahoo.com/quote/{yf_symbol}/financials/", "type": "Income Statement"})
    links.append({"name": "Yahoo Finance — Balance Sheet", "url": f"https://finance.yahoo.com/quote/{yf_symbol}/balance-sheet/", "type": "Balance Sheet"})
    links.append({"name": "Yahoo Finance — Cash Flow", "url": f"https://finance.yahoo.com/quote/{yf_symbol}/cash-flow/", "type": "Cash Flow"})

    if ticker.endswith(".NS") or exchange in ("NSI", "NSE"):
        links.append({"name": f"NSE India — {symbol_clean}", "url": f"https://www.nseindia.com/get-quotes/equity?symbol={symbol_clean}", "type": "Exchange Filing"})
        links.append({"name": f"Screener.in — {symbol_clean}", "url": f"https://www.screener.in/company/{symbol_clean}/consolidated/", "type": "Financial Summary"})
    elif ticker.endswith(".BO") or exchange in ("BSE", "BOM"):
        links.append({"name": f"BSE India — {symbol_clean}", "url": f"https://www.bseindia.com/stock-share-price/{symbol_clean.lower()}/", "type": "Exchange Filing"})
        links.append({"name": f"Screener.in — {symbol_clean}", "url": f"https://www.screener.in/company/{symbol_clean}/consolidated/", "type": "Financial Summary"})
    else:
        links.append({"name": f"SEC EDGAR — {symbol_clean}", "url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={symbol_clean}&type=10-K&owner=include&count=10", "type": "Annual Report (10-K)"})
        links.append({"name": f"Macrotrends — {symbol_clean}", "url": f"https://www.macrotrends.net/stocks/charts/{symbol_clean}/financials", "type": "Historical Financials"})

    website = info.get("website", "")
    if website:
        links.append({"name": "Company Website", "url": website, "type": "Investor Relations"})

    return links


def _df_to_dict(df: pd.DataFrame) -> dict:
    result = {}
    for row_label in df.index:
        row_data = {}
        for col in df.columns:
            val = df.loc[row_label, col]
            if pd.isna(val):
                row_data[str(col.date())] = None
            else:
                row_data[str(col.date())] = round(float(val), 2)
        result[str(row_label)] = row_data
    return result


def resolve_ticker(company_name: str) -> str | None:
    name = company_name.strip()

    # 1. yfinance Search
    try:
        results = yf.Search(name, max_results=10)
        quotes = results.quotes
        if quotes:
            for q in quotes:
                if q.get("quoteType", "").upper() in ("EQUITY", "ETF"):
                    sym = q.get("symbol", "")
                    if sym:
                        logger.info(f"Resolved '{name}' -> {sym}")
                        return sym
            sym = quotes[0].get("symbol")
            if sym:
                return sym
    except Exception as e:
        logger.warning(f"yfinance search failed: {e}")

    # 2. Direct ticker
    try:
        t = yf.Ticker(name.upper())
        if getattr(t.fast_info, "last_price", None):
            return name.upper()
    except Exception:
        pass

    # 3. Indian suffixes
    clean = name.upper().replace(" ", "").replace(".", "").replace("&", "AND")
    for suffix in [".NS", ".BO"]:
        try:
            t = yf.Ticker(clean + suffix)
            if getattr(t.fast_info, "last_price", None):
                return clean + suffix
        except Exception:
            pass

    return None


def get_chart_data(company_data: dict) -> dict:
    charts = {}
    inc = company_data.get("income_statement", {})

    revenue_row = inc.get("Total Revenue") or inc.get("Revenue")
    if revenue_row:
        dates = sorted(revenue_row.keys())
        charts["revenue"] = {"labels": dates, "values": [revenue_row[d] for d in dates], "title": "Annual Revenue", "type": "bar"}

    ni_row = inc.get("Net Income")
    if ni_row:
        dates = sorted(ni_row.keys())
        charts["net_income"] = {"labels": dates, "values": [ni_row[d] for d in dates], "title": "Net Income", "type": "bar"}

    ph = company_data.get("price_history", [])
    if ph:
        charts["price"] = {"labels": [p["date"] for p in ph], "values": [p["close"] for p in ph], "title": "Stock Price (2Y)", "type": "line"}

    cf = company_data.get("cash_flow", {})
    ocf = cf.get("Operating Cash Flow") or cf.get("Total Cash From Operating Activities")
    if ocf:
        dates = sorted(ocf.keys())
        charts["cash_flow"] = {"labels": dates, "values": [ocf[d] for d in dates], "title": "Operating Cash Flow", "type": "bar"}

    ratios = company_data.get("ratios", {})
    ratio_map = [("pe_ratio", "P/E"), ("pb_ratio", "P/B"), ("current_ratio", "Current Ratio"), ("debt_to_equity", "D/E")]
    labels, values = [], []
    for k, label in ratio_map:
        v = ratios.get(k)
        if v is not None:
            labels.append(label)
            values.append(round(v, 2))
    if values:
        charts["ratios"] = {"labels": labels, "values": values, "title": "Key Ratios", "type": "bar"}

    return charts
