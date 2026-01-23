import asyncio
import hashlib
import logging
from pathlib import Path
from typing import Optional, List, Callable, Awaitable, Dict

from logging import Logger

from asyncio.events import AbstractEventLoop
from adapters.base_adapter import BaseAdapter
from core.base_summarizer import BaseSummarizer
from custom_types.batch_result import BatchResult
from custom_types.document_result import DocumentResult
from decorators import injectable
from enums import ProcessingStatus

logger: Logger = logging.getLogger(__name__)


@injectable
class DocumentService:

    def __init__(
        self,
        summarizer: BaseSummarizer,
        adapter: Optional[BaseAdapter] = None,
        enable_cache: bool = True,
    ) -> None:
        self.adapter: Optional[BaseAdapter] = adapter
        self.summarizer: BaseSummarizer = summarizer
        self.enable_cache: bool = enable_cache
        self._cache: Dict[str, DocumentResult] = {}

    def _get_file_hash(self, file_path: str) -> str:
        path: Path = Path(file_path)
        stat = path.stat()
        key: str = f"{file_path}:{stat.st_size}:{stat.st_mtime}"
        return hashlib.md5(key.encode()).hexdigest()

    def _get_cached_result(self, file_path: str) -> Optional[DocumentResult]:
        if not self.enable_cache:
            return None
        file_hash: str = self._get_file_hash(file_path)
        return self._cache.get(file_hash)

    def _cache_result(self, file_path: str, result: DocumentResult) -> None:
        if self.enable_cache and result.is_success:
            file_hash: str = self._get_file_hash(file_path)
            self._cache[file_hash] = result

    async def process_file(self, file_path: str) -> DocumentResult:
        loop: AbstractEventLoop = asyncio.get_running_loop()
        start_time: float = loop.time()

        cached: Optional[DocumentResult] = self._get_cached_result(file_path)
        if cached:
            logger.debug(f"Cache hit: {file_path}")
            return cached

        try:
            if not self.adapter:
                raise ValueError("Adapter not set for DocumentService")

            path: Path = Path(file_path)
            if not await loop.run_in_executor(None, path.exists):
                return DocumentResult(
                    file_path=file_path,
                    status=ProcessingStatus.ERROR,
                    error_message=f"Arquivo não encontrado: {file_path}",
                )

            if not await loop.run_in_executor(None, path.is_file):
                return DocumentResult(
                    file_path=file_path,
                    status=ProcessingStatus.ERROR,
                    error_message=f"Caminho não é um arquivo: {file_path}",
                )

            logger.info(f"Processando: {path.name}")

            text: str = await self.adapter.read_text(file_path)

            if not text or not text.strip():
                return DocumentResult(
                    file_path=file_path,
                    status=ProcessingStatus.EMPTY_CONTENT,
                    error_message="Não foi possível extrair texto do arquivo",
                    processing_time_ms=(loop.time() - start_time) * 1000,
                )
            
            word_count: int = len(text.split())
            char_count: int = len(text)
            
            if word_count < 10:
                return DocumentResult(
                    file_path=file_path,
                    status=ProcessingStatus.EMPTY_CONTENT,
                    error_message=f"Texto extraído muito curto ({word_count} palavras). "
                                "Arquivo pode estar corrompido, vazio ou conter apenas imagens.",
                    processing_time_ms=(loop.time() - start_time) * 1000,
                )
            
            text_without_spaces: str = text.replace(' ', '').replace('\n', '').replace('\t', '')
            if len(text_without_spaces) < 50:
                return DocumentResult(
                    file_path=file_path,
                    status=ProcessingStatus.EMPTY_CONTENT,
                    error_message="Texto extraído contém muito poucos caracteres válidos. "
                                "Arquivo pode estar corrompido.",
                    processing_time_ms=(loop.time() - start_time) * 1000,
                )
            
            logger.debug(f"Texto validado: {word_count} palavras, {char_count} caracteres")
            
            summary: str = await self.summarizer.summarize(text)
            elapsed_ms: float = (loop.time() - start_time) * 1000

            result: DocumentResult = DocumentResult(
                file_path=file_path,
                status=ProcessingStatus.SUCCESS,
                summary=summary,
                word_count=word_count,
                processing_time_ms=elapsed_ms,
            )

            self._cache_result(file_path, result)
            logger.info(f"Concluído: {path.name} ({elapsed_ms:.0f}ms)")
            return result

        except Exception as e:
            elapsed_ms: float = (loop.time() - start_time) * 1000
            logger.error(f"Erro ao processar {file_path}: {e}", exc_info=True)
            return DocumentResult(
                file_path=file_path,
                status=ProcessingStatus.ERROR,
                error_message=str(e),
                processing_time_ms=elapsed_ms,
            )

    async def process_batch(
        self,
        file_paths: List[str],
        on_progress: Optional[Callable[[DocumentResult, int, int], None]] = None,
    ) -> BatchResult:
        if not file_paths:
            return BatchResult()

        loop: AbstractEventLoop = asyncio.get_running_loop()
        start_time: float = loop.time()
        total: int = len[str](file_paths)
        logger.info(f"Iniciando processamento de {total} arquivo(s)")

        tasks: List[Awaitable[DocumentResult]] = []
        for i, file_path in enumerate[str](file_paths):
            task: Awaitable[DocumentResult] = self._create_progress_wrapped_task(file_path, i, total, on_progress)
            tasks.append(task)
        
        results: List[DocumentResult] = await asyncio.gather(*tasks)

        elapsed_ms: float = (loop.time() - start_time) * 1000
        batch_result: BatchResult = BatchResult(results=results, total_processing_time_ms=elapsed_ms)
        logger.info(f"Batch concluído: {batch_result.summary()}")
        return batch_result

    async def _create_progress_wrapped_task(
        self,
        file_path: str,
        index: int,
        total: int,
        on_progress: Optional[Callable[[DocumentResult, int, int], None]],
    ) -> DocumentResult:
        result: DocumentResult = await self.process_file(file_path)
        if on_progress:
            on_progress(result, index + 1, total)
        return result

    def clear_cache(self) -> int:
        count: int = len(self._cache)
        self._cache.clear()
        logger.info(f"Cache limpo: {count} item(s) removido(s)")
        return count

    async def get_summary_from_file(self, file_path: str) -> str:
        result: DocumentResult = await self.process_file(file_path)
        if result.is_success:
            return result.summary
        return result.error_message or "Erro ao processar arquivo"

