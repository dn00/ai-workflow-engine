"""Build source-labeled retrieval context for prompts."""

from app.retrieval.models import RetrievalResult


def build_retrieved_context(result: RetrievalResult, *, max_chars: int = 3000) -> str:
    """Render retrieved chunks with explicit citation IDs and source labels."""
    if not result.chunks:
        return "No retrieved context."

    parts: list[str] = []
    used_chars = 0
    for chunk in result.chunks:
        header = f"[{chunk.chunk_id}] Source: {chunk.source_name} Score: {chunk.score}"
        body = chunk.text.strip()
        block = f"{header}\n{body}"
        additional = len(block) + (2 if parts else 0)
        if parts and used_chars + additional > max_chars:
            break
        parts.append(block)
        used_chars += additional

    return "\n\n".join(parts)
