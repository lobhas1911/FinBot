"""
Chunker
Splits parsed page text into overlapping chunks with metadata.
"""

from langchain.text_splitter import RecursiveCharacterTextSplitter
from app.config import CHUNK_SIZE, CHUNK_OVERLAP


def chunk_pages(pages: list[dict], company_name: str) -> list[dict]:
    """
    Takes list of page dicts and returns list of chunk dicts:
    { text, metadata: { company, url, doc_type, page, chunk_index } }
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""]
    )

    chunks = []
    for page in pages:
        raw_text = page.get("text", "").strip()
        if not raw_text:
            continue

        splits = splitter.split_text(raw_text)
        for i, split in enumerate(splits):
            chunks.append({
                "text": split,
                "metadata": {
                    "company": company_name,
                    "url": page.get("url", ""),
                    "doc_type": page.get("doc_type", "unknown"),
                    "page": page.get("page", 1),
                    "chunk_index": i
                }
            })

    return chunks
