from numpy._core.numerictypes import str_
from pypdf._page import PageObject


import asyncio
import logging
from pypdf import PdfReader
from pypdf.errors import PdfReadError, WrongPasswordError, FileNotDecryptedError
from .base_adapter import BaseAdapter
from asyncio.events import AbstractEventLoop

logger = logging.getLogger(__name__)


def _read_pdf_file(file_path: str) -> str:
    try:
        text: str = ""
        with open(file_path, "rb") as file:
            try:
                reader: PdfReader = PdfReader(file)
                
                if reader.is_encrypted:
                    raise ValueError(
                        f"PDF protegido por senha: {file_path}. "
                        "Não é possível extrair texto sem a senha."
                    )
                
                num_pages: int = len(reader.pages)
                if num_pages == 0:
                    raise ValueError(f"PDF vazio (sem páginas): {file_path}")
                
                logger.debug(f"Processando PDF com {num_pages} páginas: {file_path}")
                
                pages_with_text: int = 0
                for i, page in enumerate[PageObject](reader.pages):
                    try:
                        page_text: str = page.extract_text() or ""
                        if page_text.strip():
                            text += page_text + "\n"
                            pages_with_text += 1
                    except Exception as e:
                        logger.warning(f"Erro ao extrair texto da página {i+1}: {e}")
                        continue
                
                if not text.strip():
                    raise ValueError(
                        f"PDF não contém texto extraível (pode ser apenas imagens): {file_path}. "
                        "Considere usar OCR."
                    )
                
                if pages_with_text < num_pages * 0.1:  # Menos de 10% das páginas
                    logger.warning(
                        f"Apenas {pages_with_text}/{num_pages} páginas contêm texto. "
                        "PDF pode ter problemas de OCR ou estar corrompido."
                    )
                
                logger.debug(f"Extraído {len(text)} caracteres de {pages_with_text} páginas")
                return text
                
            except (WrongPasswordError, FileNotDecryptedError):
                raise ValueError(
                    f"PDF protegido por senha: {file_path}. "
                    "Não é possível extrair texto sem a senha."
                )
            except PdfReadError as e:
                raise ValueError(
                    f"PDF corrompido ou inválido: {file_path}. "
                    f"Erro: {e}"
                )
                
    except FileNotFoundError:
        raise IOError(f"Arquivo não encontrado: {file_path}")
    except PermissionError:
        raise IOError(f"Sem permissão para ler o arquivo: {file_path}")
    except ValueError:
        raise  # Re-raise ValueError
    except Exception as e:
        raise IOError(f"Erro inesperado ao ler o arquivo PDF '{file_path}': {e}")


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
