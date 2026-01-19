from typing import Optional

from adapters.faiss_adapter import FaissAdapter
from decorators.injectable_decorator import injectable

@injectable
class FaissAdapterBuilder:
    def __init__(self) -> None:
        self._text: Optional[str] = None

    def with_text(self, text: str) -> "FaissAdapterBuilder":
        self._text: str = text
        return self

    def build(self) -> FaissAdapter:
        adapter: FaissAdapter = FaissAdapter()
        if self._text:
            adapter.chunks = adapter.chunk_text(self._text)
        return adapter


