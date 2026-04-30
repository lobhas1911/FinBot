"""
RAG Engine
Retrieves relevant chunks and generates grounded, cited answers via LLM.
"""

import logging
from app import vector_store
from app.config import LLM_PROVIDER, LLM_MODEL, OPENAI_API_KEY, GEMINI_API_KEY, TOP_K_CHUNKS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a professional financial analyst assistant.
Your job is to answer questions about a company's financials using ONLY the source excerpts provided below.

Rules:
- Answer based strictly on the provided sources. Do not use outside knowledge.
- For every factual claim, add a citation like [Source N] referencing the source number.
- If the answer cannot be found in the sources, clearly state: "This information is not available in the loaded documents."
- Be concise, structured, and use bullet points or tables where appropriate.
- When discussing numbers, always mention the time period they refer to.
"""


def answer(company: str, question: str) -> dict:
    """
    Retrieve relevant chunks and generate an LLM answer with citations.
    Returns { "answer": str, "sources": list[dict] }
    """
    chunks = vector_store.search(company, question, top_k=TOP_K_CHUNKS)

    if not chunks:
        return {
            "answer": "No relevant information found in the loaded documents.",
            "sources": []
        }

    # Build source context block
    source_block = ""
    for i, chunk in enumerate(chunks):
        meta = chunk["metadata"]
        source_label = f"[Source {i+1}]"
        source_info = f"Document: {meta.get('url', 'unknown')} | Page: {meta.get('page', '?')} | Type: {meta.get('doc_type', '?')}"
        source_block += f"\n{source_label} {source_info}\n{chunk['text']}\n"

    user_message = f"""Sources:
{source_block}

Question: {question}

Answer (cite sources inline using [Source N]):"""

    response_text = _call_llm(user_message)

    return {
        "answer": response_text,
        "sources": [
            {
                "index": i + 1,
                "url": c["metadata"].get("url", ""),
                "page": c["metadata"].get("page", 1),
                "doc_type": c["metadata"].get("doc_type", ""),
                "snippet": c["text"][:200] + "..."
            }
            for i, c in enumerate(chunks)
        ]
    }


def _call_llm(user_message: str) -> str:
    if LLM_PROVIDER == "gemini":
        return _gemini_chat(user_message)
    return _openai_chat(user_message)


def _openai_chat(user_message: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ],
        temperature=0.2,
        max_tokens=1500
    )
    return resp.choices[0].message.content.strip()


def _gemini_chat(user_message: str) -> str:
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name="models/gemini-2.5-flash",
        system_instruction=SYSTEM_PROMPT
    )
    resp = model.generate_content(user_message)
    return resp.text.strip()
