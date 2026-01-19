import re
from typing import List

import asyncio
import re
from typing import List
from asyncio.events import AbstractEventLoop

from docx import Document as DocxDocument

from .base_adapter import BaseAdapter


def _read_docx_file(file_path: str) -> str:
    try:
        doc: DocxDocument = DocxDocument(file_path)
        full_text: List[str] = [para.text for para in doc.paragraphs]
        return "\n".join(full_text)
    except Exception as e:
        raise IOError(f"Erro ao ler o arquivo DOCX '{file_path}': {e}")


class DocxAdapter(BaseAdapter):

    def chunk(self, text: str) -> List[str]:
        paragraphs: List[str] = re.split(r"\n+", text)
        paragraphs: List[str] = [p.strip() for p in paragraphs if p.strip()]
        return paragraphs

    async def read_text(self, file_path: str) -> str:
        loop: AbstractEventLoop = asyncio.get_running_loop()

        text: str = await loop.run_in_executor(None, _read_docx_file, file_path)
        return text


if __name__ == "__main__":
    adapter: DocxAdapter = DocxAdapter()
    print("Adaptador DOCX pronto para ser usado.")
