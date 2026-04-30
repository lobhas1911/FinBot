import os
from dotenv import load_dotenv

load_dotenv()

GROK_API_KEY = os.getenv("GROK_API_KEY", "")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "grok")
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "grok")

LLM_MODEL = os.getenv("LLM_MODEL", "grok-3-mini")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "grok-3-mini")

VECTOR_STORE_PATH = os.getenv("VECTOR_STORE_PATH", "./data/vector_stores")

# RAG settings (kept for compatibility)
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
TOP_K_CHUNKS = 6
MAX_DOCS_PER_SESSION = 10

# Groq base URL (OpenAI-compatible)
GROK_BASE_URL = "https://api.groq.com/openai/v1"
