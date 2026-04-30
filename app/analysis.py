"""
Analysis Engine
Sends structured financial data to Grok LLM and returns formatted analysis.
"""

import logging
from app.config import LLM_MODEL, GROK_API_KEY, GROK_BASE_URL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert financial analyst and investment advisor with deep knowledge of:
- Financial statement analysis (income statement, balance sheet, cash flow)
- Valuation methodologies (DCF, comparable company analysis, asset-based)
- Financial ratios and what they mean in context
- Industry benchmarks and sector-specific metrics
- Indian and global capital markets
- Accounting principles (GAAP, Ind AS, IFRS)

When answering questions:
- USE the provided financial data as your primary source
- ALSO apply your own financial expertise to calculate derived metrics, make comparisons, and provide context
- CALCULATE things the user asks for — CAGR, growth rates, margins, ratios — show your working
- COMPARE metrics to industry norms and benchmarks even if not in the data
- INTERPRET what the numbers mean, not just report them
- If data for something is missing, use your knowledge to estimate or explain what it would typically indicate
- Be specific with numbers, always mention time periods
- Structure answers clearly with sections when needed
- Format monetary values readably (e.g. ₹1,234 Cr or $1.2B)
"""


def analyze(company_data: dict, question: str = None) -> str:
    context = _build_context(company_data)
    name = company_data['info'].get('name', company_data['ticker'])

    if question:
        prompt = f"""You are analyzing {name}.

Here is the complete financial data available:
{context}

User Question: {question}

Instructions:
- Answer the question directly and thoroughly
- If the question requires calculation (CAGR, growth rate, margin, ratio), SHOW the calculation step by step
- If the question asks for comparison or benchmarking, use your knowledge of industry standards
- If the question asks for opinion or recommendation, provide a well-reasoned view based on the data
- If specific data is missing, say so but still provide what insight you can from available data and general knowledge
- Use bullet points, tables, or numbered steps where it makes the answer clearer"""
    else:
        prompt = f"""You are analyzing {name}.

Here is the complete financial data available:
{context}

Provide a comprehensive fundamental analysis. Cover:

## 1. Business Overview
Brief description of what the company does, its sector, and scale.

## 2. Revenue & Profitability
- Revenue trend with growth rates (calculate CAGR if multiple years available)
- Gross margin, operating margin, net margin trends
- What the margins tell us about the business quality

## 3. Balance Sheet Health
- Asset base and composition
- Debt levels and debt-to-equity ratio interpretation
- Liquidity (current ratio, cash position)

## 4. Cash Flow Analysis
- Operating cash flow trend
- Free cash flow generation
- Capital allocation quality

## 5. Valuation
- Current P/E, P/B, and what they imply
- Whether the stock looks cheap, fair, or expensive vs typical sector multiples

## 6. Key Strengths & Risks
- 3-4 concrete strengths backed by numbers
- 3-4 concrete risks or concerns

## 7. Overall Assessment
A clear, direct verdict on the company's financial health and investment attractiveness."""

    return _call_grok(prompt)


def _build_context(data: dict) -> str:
    parts = []

    info = data.get("info", {})
    parts.append(f"Company: {info.get('name')} | Sector: {info.get('sector')} | Industry: {info.get('industry')}")
    parts.append(f"Country: {info.get('country')} | Currency: {info.get('currency')} | Exchange: {info.get('exchange')}")
    if info.get("market_cap"):
        parts.append(f"Market Cap: {_fmt(info['market_cap'])}")
    if info.get("employees"):
        parts.append(f"Employees: {info['employees']:,}")
    if info.get("description"):
        parts.append(f"Description: {info['description'][:300]}")

    # Key ratios only
    ratios = data.get("ratios", {})
    if ratios:
        parts.append("\n--- KEY RATIOS ---")
        ratio_map = {
            "current_price": "Price", "pe_ratio": "P/E", "forward_pe": "Fwd P/E",
            "pb_ratio": "P/B", "debt_to_equity": "D/E", "current_ratio": "Current Ratio",
            "roe": "ROE", "profit_margin": "Net Margin", "operating_margin": "Op Margin",
            "gross_margin": "Gross Margin", "revenue_growth": "Rev Growth YoY",
            "earnings_growth": "EPS Growth YoY", "dividend_yield": "Div Yield",
            "beta": "Beta", "52w_high": "52W High", "52w_low": "52W Low",
        }
        for k, label in ratio_map.items():
            v = ratios.get(k)
            if v is not None:
                if k in ("roe", "profit_margin", "operating_margin", "gross_margin",
                         "revenue_growth", "earnings_growth", "dividend_yield"):
                    parts.append(f"{label}: {v*100:.2f}%")
                else:
                    parts.append(f"{label}: {v}")

    # Income statement — key rows only, last 4 years max
    inc = data.get("income_statement", {})
    key_inc = ["Total Revenue", "Revenue", "Gross Profit", "Operating Income", "Net Income", "EBITDA", "Basic EPS"]
    if inc:
        parts.append("\n--- INCOME STATEMENT ---")
        for row in key_inc:
            if row in inc:
                vals = {k: _fmt(v) for k, v in sorted(inc[row].items()) if v is not None}
                if vals:
                    parts.append(f"{row}: {vals}")

    # Balance sheet — key rows only
    bs = data.get("balance_sheet", {})
    key_bs = ["Total Assets", "Total Liabilities Net Minority Interest",
              "Total Equity Gross Minority Interest", "Cash And Cash Equivalents",
              "Total Debt", "Current Assets", "Current Liabilities"]
    if bs:
        parts.append("\n--- BALANCE SHEET ---")
        for row in key_bs:
            if row in bs:
                vals = {k: _fmt(v) for k, v in sorted(bs[row].items()) if v is not None}
                if vals:
                    parts.append(f"{row}: {vals}")

    # Cash flow — key rows only
    cf = data.get("cash_flow", {})
    key_cf = ["Operating Cash Flow", "Free Cash Flow", "Capital Expenditure",
              "Total Cash From Operating Activities"]
    if cf:
        parts.append("\n--- CASH FLOW ---")
        for row in key_cf:
            if row in cf:
                vals = {k: _fmt(v) for k, v in sorted(cf[row].items()) if v is not None}
                if vals:
                    parts.append(f"{row}: {vals}")

    return "\n".join(parts)


def _fmt(val) -> str:
    if val is None:
        return "N/A"
    try:
        val = float(val)
        if abs(val) >= 1e12: return f"{val/1e12:.2f}T"
        if abs(val) >= 1e9:  return f"{val/1e9:.2f}B"
        if abs(val) >= 1e6:  return f"{val/1e6:.2f}M"
        if abs(val) >= 1e3:  return f"{val/1e3:.2f}K"
        return str(round(val, 2))
    except Exception:
        return str(val)


def _call_grok(prompt: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=GROK_API_KEY, base_url=GROK_BASE_URL)
    try:
        resp = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1500
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        err = str(e)
        if "429" in err or "quota" in err.lower() or "rate" in err.lower():
            raise RuntimeError("Grok API rate limit reached. Please wait a moment and try again.")
        raise
