# FinBot
Repository contains a chatbot that performs Fundamental Financial Analysis of companies listed on stock indices across multiple stock exchanges around the world.

OverviewThis chatbot enables users to perform deep financial analysis on listed companies through natural language queries. It combines real-time market data fetching, uploaded document processing with semantic search, and AI-powered interpretation to deliver actionable financial insights.Key Features
Natural Language Query Processing - Ask questions about company fundamentals, growth, valuations, and trends in plain English
Document Upload & RAG Pipeline - Upload annual reports, financial statements (PDF, Excel, images), extract text via OCR, embed into vector DB, and retrieve relevant sections for analysis
Multi-Source Data Aggregation - Pulls balance sheets, income statements, and ratios from yfinance, screener.in, and moneycontrol via web scraping
Intelligent Intent Classification - Automatically identifies query type (fundamentals, price trends, growth analysis, comparative analysis) and routes to appropriate analysis module
Balance Sheet Deep Dive - Calculates financial ratios (current ratio, debt-to-equity, ROE, margins), detects trends year-over-year, and flags anomalies
Real-Time Visualizations - Generates doughnut and line charts for asset composition, liability trends, and equity evolution
Session-Based Authentication - Secure multi-user access with 8-hour session TTL and role-based features
Query Logging & Audit Trail - Every query logged with timestamp, user, intent, and LLM response for compliance and debugging
Technical StackBackend Framework

FastAPI 0.115.0 - Async web framework
Uvicorn 0.30.6 - ASGI server
Python 3.10+ - Core language
Data & Analysis

Pandas 2.2.2 - DataFrame operations, time-series analysis
NumPy 1.26.4 - Numerical computations
yfinance 0.2.40 - Stock data, balance sheets, financial statements
BeautifulSoup4 4.12.3 - HTML/XML parsing for web scraping
requests 2.32.3 - HTTP client for API calls
lxml 5.2.2 - Fast XML/HTML processing
LLM & NLP

Groq 0.11.0 - LLM API client (llama-3.3-70b-versatile model)
(Planned) Langchain/LangGraph - Agentic orchestration
(Planned) Sentence Transformers - Embedding generation for documents
RAG & Vector Store

(Planned) Chroma - Local vector database for document embeddings
(Planned) FAISS - Fast similarity search for semantic retrieval
(Planned) PyPDF2 - PDF text extraction
(Planned) python-pptx - PowerPoint parsing
Frontend

Vanilla JavaScript - DOM manipulation, API calls
Chart.js 4.4.1 - Interactive data visualizations
HTML5 & CSS3 - Responsive UI with dark theme
Document Processing

openpyxl 3.1.5 - Excel file parsing
(Planned) Tesseract OCR - Scanned document text extraction
(Planned) python-docx - Word document parsing
Utilities

python-dotenv 1.0.1 - Environment variable management
python-multipart 0.0.9 - Form data handling
Pydantic 2.8.2 - Data validation
fake-useragent 1.5.1 - Web scraping user agent rotation

┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Vanilla JS)                    │
│  Query Input │ Document Upload │ Chat Interface │ Visualizations
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
   ┌──────────┐    ┌──────────┐    ┌──────────┐
   │  Auth    │    │  Query   │    │ Document │
   │ Module   │    │ Engine   │    │ Upload   │
   └──────────┘    └────┬─────┘    └────┬─────┘
                        │               │
        ┌───────────────┼───────────────┘
        │               │
        ▼               ▼
   ┌────────────────────────────────┐
   │   Data Processing Pipeline     │
   │  ┌──────────────────────────┐  │
   │  │ Intent Classification    │  │
   │  └──────────────────────────┘  │
   │  ┌──────────────────────────┐  │
   │  │ Multi-Source Fetchers    │  │
   │  │ (yfinance, scrapers)     │  │
   │  └──────────────────────────┘  │
   │  ┌──────────────────────────┐  │
   │  │ RAG Pipeline             │  │
   │  │ (Embed, Retrieve, Rank)  │  │
   │  └──────────────────────────┘  │
   │  ┌──────────────────────────┐  │
   │  │ Financial Analysis       │  │
   │  │ (Ratios, Trends, Flags)  │  │
   │  └──────────────────────────┘  │
   └────────────┬───────────────────┘
                │
                ▼
   ┌────────────────────────────────┐
   │   LLM Integration (Groq)       │
   │   Intent-Aware Prompting       │
   │   Context Window Management    │
   └────────────┬───────────────────┘
                │
                ▼
   ┌────────────────────────────────┐
   │   Response Formatting          │
   │   Chart Config Generation      │
   │   Audit Logging                │
   └────────────────────────────────┘
