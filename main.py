import asyncio
import logging
import sys
from logging import Logger
from pathlib import Path
from typing import List, Dict, Union

from dotenv import load_dotenv

import config
from adapters import DocxAdapter, PdfAdapter, BaseAdapter
from core.base_summarizer import BaseSummarizer
from core.openai_summarizer import OpenAISummarizer
from core.anti_hallucination_summarizer import AntiHallucinationSummarizer
from custom_types.batch_result import BatchResult
from custom_types.document_result import DocumentResult
from services.document_service import DocumentService
from utils.file_utils import find_files, move_file_to_processed


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def print_progress(result: DocumentResult, current: int, total: int) -> None:
    status: str = "✓" if result.is_success else "✗"
    logging.info(f"  [{current}/{total}] {status} {result.file_name}")


def print_batch_results(batch: BatchResult, title: str) -> None:
    logging.info(f"\n{'='*60}")
    logging.info(f" {title}")
    logging.info(f"{ '='*60}")

    if not batch.results:
        logging.info("  Nenhum arquivo processado.")
        return

    logging.info(f"\n📊 {batch.summary()}\n")

    successful: List[DocumentResult] = batch.get_successful()

    if successful:
        logging.info("📄 Resumos gerados:")
        logging.info("-" * 40)
        for result in successful:
            logging.info(f"\n▶ {result.file_name}")
            logging.info(
                f"  Palavras: {result.word_count} | Tempo: {result.processing_time_ms:.0f}ms"
            )
            logging.info(f"  {result.summary}")

    errors: List[DocumentResult] = batch.get_errors()

    if errors:
        logging.info("\n⚠️  Erros encontrados:")
        logging.info("-" * 40)
        for result in errors:
            logging.info(f"  ✗ {result.file_name}: {result.error_message}")


async def main() -> None:
    setup_logging()
    logger: Logger = logging.getLogger(__name__)

    load_dotenv()

    logger.info("\n" + "=" * 60)
    logger.info(" 📚 BOT DE SUMARIZAÇÃO DE PROCESSOS (ASYNC)")
    logger.info("=" * 60)

    # Usa as pastas do projeto Velida 001
    input_path: Path = Path(config.VELIDA_INPUT_DIR)
    output_path: Path = Path(config.VELIDA_OUTPUT_DIR)

    # Cria as pastas automaticamente se não existirem (entrada e saída)
    # parents=True cria todos os diretórios intermediários necessários
    # exist_ok=True evita erro se o diretório já existir
    input_path.mkdir(parents=True, exist_ok=True)
    output_path.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"📁 Pasta de entrada: {config.VELIDA_INPUT_DIR}")
    logger.info(f"📁 Pasta de concluídos: {config.VELIDA_OUTPUT_DIR}")

    # Escolhe o sumarizador baseado na configuracao
    try:
        summarizer: BaseSummarizer
        if config.PIPELINE_MODE == "anti_hallucination":
            logger.info("Modo: ANTI-ALUCINACAO (pipeline de 6 camadas)")
            summarizer = AntiHallucinationSummarizer(
                model=config.EXTRACTION_MODEL,
                chunker_max_words=config.CHUNKER_MAX_WORDS,
                extraction_max_parallel=config.EXTRACTION_MAX_PARALLEL,
                extraction_temperature=config.EXTRACTION_TEMPERATURE,
                consolidation_temperature=config.CONSOLIDATION_TEMPERATURE,
                generation_temperature=config.GENERATION_TEMPERATURE,
                max_regeneration_attempts=config.MAX_REGENERATION_ATTEMPTS,
            )
        else:
            logger.info("Modo: LEGACY (sumarizacao simples)")
            summarizer = OpenAISummarizer()
    except ValueError as e:
        logger.error(f"Erro ao inicializar o sumarizador: {e}")
        logger.info(
            "\n Certifique-se de que a variavel de ambiente OPENAI_API_KEY esta definida no seu arquivo .env"
        )
        return

    adapters: Dict[str, BaseAdapter] = {
        ".pdf": PdfAdapter(),
        ".docx": DocxAdapter(),
    }

    # Busca arquivos na pasta de entrada (A Fazer)
    all_files: List[str] = []
    for ext in adapters.keys():
        all_files.extend(find_files(config.VELIDA_INPUT_DIR, ext))

    total_files: int = len(all_files)

    logger.info(
        f"\n🔍 Encontrados: {len(all_files)} arquivo(s) para processar ({len([f for f in all_files if f.endswith('.pdf')])} PDF(s), {len([f for f in all_files if f.endswith('.docx')])} DOCX(s))"
    )

    if total_files == 0:
        logger.info(f"\n⚠️  Nenhum arquivo encontrado em '{config.VELIDA_INPUT_DIR}'")
        logger.info("   Adicione arquivos PDF ou DOCX na pasta 'A Fazer' para processamento.")
        return

    async def process_file_with_correct_adapter(file_path: str, p_bar: dict) -> DocumentResult:
        """
        Processa um arquivo com o adaptador correto e move para a pasta de concluídos se bem-sucedido.
        
        Args:
            file_path: Caminho do arquivo a ser processado
            p_bar: Dicionário com informações de progresso (current, total)
        
        Returns:
            DocumentResult com o resultado do processamento
        """
        ext: str = Path(file_path).suffix
        adapter: BaseAdapter = adapters[ext]
        document_service: DocumentService = DocumentService(
            adapter=adapter, summarizer=summarizer
        )
        
        # Processa o arquivo
        result: DocumentResult = await document_service.process_file(file_path)
        
        # Se o processamento foi bem-sucedido, move o arquivo para a pasta de concluídos
        if result.is_success:
            moved: bool = await asyncio.get_event_loop().run_in_executor(
                None, 
                move_file_to_processed, 
                file_path, 
                config.VELIDA_OUTPUT_DIR
            )
            if moved:
                logger.info(f"✅ Arquivo movido para '{config.VELIDA_OUTPUT_DIR}': {Path(file_path).name}")
            else:
                logger.warning(f"⚠️  Não foi possível mover o arquivo: {Path(file_path).name}")
        
        p_bar["current"] += 1
        print_progress(result, p_bar["current"], p_bar["total"])
        return result

    p_bar_info: Dict[str, int] = {"current": 0, "total": total_files}
    
    # Limita processamento paralelo para evitar sobrecarga de memória/API
    # REDUZIDO para 1 arquivo por vez para evitar rate limits com documentos grandes
    MAX_PARALLEL_FILES: int = 1  # Processa 1 arquivo por vez (documentos grandes geram muitos chunks)
    semaphore: asyncio.Semaphore = asyncio.Semaphore(MAX_PARALLEL_FILES)
    
    async def process_with_limit(file_path: str) -> DocumentResult:
        async with semaphore:
            return await process_file_with_correct_adapter(file_path, p_bar_info)
    
    tasks = [process_with_limit(file) for file in all_files]
    
    results: List[DocumentResult] = await asyncio.gather(*tasks)

    batch_result: BatchResult = BatchResult(results=results)

    print_batch_results(batch_result, "RESULTADOS - TODOS OS ARQUIVOS")

    logger.info("\n" + "=" * 60)
    logger.info(" ✅ PROCESSAMENTO FINALIZADO")
    logger.info("=" * 60 + "\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Processamento cancelado pelo usuário.")
        sys.exit(0)
