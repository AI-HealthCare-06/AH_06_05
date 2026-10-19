"""근거 검색과 판정 (RAG). 챗봇 서버는 `search()`만 부른다."""

from app.services.rag.pipeline import Evidence, SearchResult, search

__all__ = ["Evidence", "SearchResult", "search"]
