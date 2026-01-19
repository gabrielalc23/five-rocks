from typing import List

def chunk_text(text: str, max_words: int = 600) -> List[str]:
    if not text:
        return []

    words: List[str] = text.split()

    return [
        " ".join(words[i:i + max_words])
        for i in range(0, len(words), max_words)
    ]