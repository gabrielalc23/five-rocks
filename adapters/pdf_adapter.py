import asyncio
from pypdf import PdfReader
from .base_adapter import BaseAdapter
from asyncio.events import AbstractEventLoop


def _read_pdf_file(file_path: str) -> str:
    try:
        text: str = ""
        with open(file_path, "rb") as file:
            reader: PdfReader = PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() or ""
        return text
    except Exception as e:
        raise IOError(f"Erro ao ler o arquivo PDF '{file_path}': {e}")


class PdfAdapter(BaseAdapter):
    def __init__(self) -> None:
        super().__init__()

    async def read_text(self, file_path: str) -> str:
        loop: AbstractEventLoop = asyncio.get_running_loop()
        text: str = await loop.run_in_executor(None, _read_pdf_file, file_path)
        return text


if __name__ == "__main__":
    adapter: PdfAdapter = PdfAdapter()
    print("Adaptador PDF pronto para ser usado.")
