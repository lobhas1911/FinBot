"""
Ingestion Orchestrator
Coordinates discovery → parsing → chunking → indexing for a company.
Yields progress events (for SSE streaming to frontend).
"""

import logging
from app import discovery, parsers, chunker, vector_store

logger = logging.getLogger(__name__)


def ingest_company(company_name: str):
    """
    Generator that yields progress dicts and performs full ingestion.
    Usage: for event in ingest_company("Infosys"): ...
    """
    yield {"status": "discovering", "message": f"Searching for financial documents for '{company_name}'..."}

    sources = discovery.discover_sources(company_name)

    if not sources:
        yield {"status": "error", "message": "No financial documents found. Please check the company name."}
        return

    yield {
        "status": "sources_found",
        "message": f"Found {len(sources)} sources. Starting ingestion...",
        "sources": sources
    }

    all_chunks = []
    loaded_sources = []
    failed_sources = []

    for i, source in enumerate(sources):
        yield {
            "status": "parsing",
            "message": f"Processing ({i+1}/{len(sources)}): {source['title']}",
            "current_source": source
        }

        try:
            pages = parsers.parse_source(source)
            if not pages:
                failed_sources.append({**source, "reason": "No text extracted"})
                yield {"status": "skipped", "message": f"Skipped (no text): {source['title']}"}
                continue

            chunks = chunker.chunk_pages(pages, company_name)
            if not chunks:
                failed_sources.append({**source, "reason": "No chunks produced"})
                continue

            all_chunks.extend(chunks)
            loaded_sources.append({**source, "chunk_count": len(chunks)})
            yield {
                "status": "parsed",
                "message": f"Loaded: {source['title']} ({len(chunks)} chunks)",
                "source": source
            }

        except Exception as e:
            logger.error(f"Ingestion failed for {source['url']}: {e}")
            failed_sources.append({**source, "reason": str(e)})
            yield {"status": "skipped", "message": f"Failed: {source['title']} — {e}"}

    if not all_chunks:
        yield {"status": "error", "message": "All documents failed to parse. No data available for chat."}
        return

    yield {"status": "indexing", "message": f"Building search index from {len(all_chunks)} chunks..."}

    try:
        vector_store.build_index(company_name, all_chunks)
    except Exception as e:
        yield {"status": "error", "message": f"Indexing failed: {e}"}
        return

    yield {
        "status": "complete",
        "message": f"Ready. Loaded {len(loaded_sources)} documents, {len(all_chunks)} chunks indexed.",
        "loaded_sources": loaded_sources,
        "failed_sources": failed_sources,
        "total_chunks": len(all_chunks)
    }
