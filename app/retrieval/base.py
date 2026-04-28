"""Retriever interface."""

from abc import ABC, abstractmethod

from app.retrieval.models import RetrievalResult


class AbstractRetriever(ABC):
    """Abstract retrieval boundary."""

    @abstractmethod
    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: dict | None = None,
    ) -> RetrievalResult: ...
