from typing import List

import faiss
from faiss import IndexFlatL2

from .base_adapter import BaseAdapter


class FaissAdapter(BaseAdapter):
    def __init__(self, embedding_dim: int = 384) -> None:
        super().__init__()
        self.embedding_dim: int = embedding_dim
        self.index: IndexFlatL2 = faiss.IndexFlatL2(self.embedding_dim)
        self.chunks: List[str] = []

    def read_text(self, parts: List[str]) -> str:
        return "\n".join(parts)

    def chunk_text(self, text: str, max_words: int = 600) -> List[str]:
        words: List[str] = text.split()
        chunks: List[str] = []

        for i in range(0, len(words), max_words):
            chunk: str = " ".join(words[i:i + max_words])
            chunks.append(chunk)
        return chunks

    def add_embeddings(self, embeddings) -> None:
        self.index.add(embeddings)

    def save_index(self, path: str = "index.faiss") -> None:
        faiss.write_index(self.index, path)

    def load_index(self, path: str = "index.faiss") -> None:
        self.index = faiss.read_index(path)
