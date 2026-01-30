"""
Orquestrador do pipeline anti-alucinacao.

Coordena as 6 camadas do pipeline para gerar resumos
estruturados sem alucinacoes.
"""

import asyncio
import json
import logging
import os
from typing import List, Dict, Any, Optional

from core.base_summarizer import BaseSummarizer
from core.factual_extractor import FactualExtractor
from core.semantic_consolidator import SemanticConsolidator
from core.section_generator import SectionGenerator
from custom_types.extraction_types import (
    ChunkExtraction,
    ConsolidatedTheme,
    SectionResult,
    PipelineResult,
)
from custom_types.process_memory import ProcessMemory
from utils.legal_chunker import LegalChunker, LegalChunk
from utils.pipeline_validator import PipelineValidator

logger = logging.getLogger(__name__)


class AntiHallucinationSummarizer(BaseSummarizer):
    """
    Sumarizador anti-alucinacao que implementa o pipeline de 6 camadas.

    Camadas:
    1. Chunker Juridico: Divide por unidade logica
    2. Extrator Factual: Extrai fatos literais (modo robo)
    3. Process Memory: Indexa extracoes por tema/evento
    4. Consolidador Semantico: Resolve conflitos (modo juiz)
    5. Gerador de Secoes: Gera 9 secoes (modo redator)
    6. Validador: Valida e dispara re-geracao

    Implementa BaseSummarizer para compatibilidade com DocumentService.
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        # Layer 1: Chunking
        chunker_max_words: int = 3000,
        # Layer 2: Extraction
        extraction_max_parallel: int = 3,
        extraction_temperature: float = 0.0,
        # Layer 4/5: Consolidation/Generation
        consolidation_temperature: float = 0.1,
        generation_temperature: float = 0.2,
        # Layer 6: Validation
        max_regeneration_attempts: int = 2,
    ):
        """
        Inicializa o pipeline anti-alucinacao.

        Args:
            model: Modelo OpenAI para todas as camadas
            api_key: Chave da API OpenAI
            chunker_max_words: Palavras maximas por chunk
            extraction_max_parallel: Extracoes paralelas
            extraction_temperature: Temperatura para extracao
            consolidation_temperature: Temperatura para consolidacao
            generation_temperature: Temperatura para geracao
            max_regeneration_attempts: Tentativas de re-geracao
        """
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")

        if not self.api_key:
            raise ValueError(
                "API key da OpenAI nao encontrada. "
                "Defina a variavel de ambiente OPENAI_API_KEY."
            )

        # Layer 1: Chunker
        self.chunker = LegalChunker(max_words=chunker_max_words)

        # Layer 2: Factual Extractor
        self.extractor = FactualExtractor(
            model=model,
            api_key=self.api_key,
            max_parallel=extraction_max_parallel,
            temperature=extraction_temperature,
        )

        # Layer 3: Process Memory (criada por execucao)
        self.memory: Optional[ProcessMemory] = None

        # Layer 4: Semantic Consolidator
        self.consolidator = SemanticConsolidator(
            model=model,
            api_key=self.api_key,
            temperature=consolidation_temperature,
        )

        # Layer 5: Section Generator
        self.generator = SectionGenerator(
            model=model,
            api_key=self.api_key,
            temperature=generation_temperature,
        )

        # Layer 6: Validator
        self.validator = PipelineValidator(
            max_regeneration_attempts=max_regeneration_attempts
        )

        self.max_regeneration_attempts = max_regeneration_attempts

    async def summarize(self, text: str, prompt: Optional[str] = None) -> str:
        """
        Executa o pipeline completo de sumarizacao.

        Args:
            text: Texto do documento
            prompt: Prompt adicional (ignorado, usa pipeline)

        Returns:
            JSON estruturado do resumo
        """
        if not text or not text.strip():
            return json.dumps({"erro": "Texto vazio"}, ensure_ascii=False)

        loop = asyncio.get_event_loop()
        start_time = loop.time()

        logger.info("=" * 60)
        logger.info("PIPELINE ANTI-ALUCINACAO INICIADO")
        logger.info("=" * 60)

        try:
            # ===== LAYER 1: Juridical Chunking =====
            chunks = self._layer1_chunking(text)

            # ===== LAYER 2: Factual Extraction =====
            extractions = await self._layer2_extraction(chunks)

            # ===== LAYER 3: Process Memory =====
            self._layer3_memory(extractions)

            # ===== LAYER 4: Semantic Consolidation =====
            consolidated = await self._layer4_consolidation()

            # ===== LAYER 5: Section Generation =====
            sections = await self._layer5_generation(consolidated)

            # ===== LAYER 6: Validation + Re-generation =====
            final_sections = await self._layer6_validation(sections, consolidated)

            # ===== Build Final Result =====
            elapsed_ms = (loop.time() - start_time) * 1000

            result = self._build_final_result(
                final_sections,
                len(chunks),
                len(extractions),
                len(consolidated),
                elapsed_ms
            )

            logger.info("=" * 60)
            logger.info(f"PIPELINE CONCLUIDO em {elapsed_ms:.0f}ms")
            logger.info("=" * 60)

            return json.dumps(result.to_json(), ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"Erro no pipeline: {e}", exc_info=True)
            return json.dumps({
                "erro": str(e),
                "pipeline_stage": "unknown"
            }, ensure_ascii=False)

    def _layer1_chunking(self, text: str) -> List[LegalChunk]:
        """
        Layer 1: Divide documento em chunks juridicos.

        Args:
            text: Texto completo

        Returns:
            Lista de LegalChunk
        """
        logger.info("-" * 40)
        logger.info("Layer 1: Juridical chunking")

        chunks = self.chunker.chunk(text)

        logger.info(f"  -> {len(chunks)} chunks criados")
        for chunk in chunks[:3]:  # Log primeiros 3
            logger.debug(f"     - {chunk.chunk_id}: {chunk.tipo_provavel} ({chunk.palavra_count} palavras)")

        return chunks

    async def _layer2_extraction(
        self,
        chunks: List[LegalChunk]
    ) -> List[ChunkExtraction]:
        """
        Layer 2: Extrai fatos de cada chunk.

        Args:
            chunks: Lista de chunks

        Returns:
            Lista de ChunkExtraction
        """
        logger.info("-" * 40)
        logger.info("Layer 2: Factual extraction")

        extractions = await self.extractor.extract_from_chunks(chunks)

        logger.info(f"  -> {len(extractions)} extracoes bem-sucedidas")

        # Log estatisticas de temas
        tema_counts: Dict[str, int] = {}
        for ext in extractions:
            for tema in ext.temas:
                tema_counts[tema.value] = tema_counts.get(tema.value, 0) + 1

        if tema_counts:
            top_temas = sorted(tema_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            logger.debug(f"  Temas mais frequentes: {top_temas}")

        return extractions

    def _layer3_memory(self, extractions: List[ChunkExtraction]) -> None:
        """
        Layer 3: Armazena extracoes na memoria indexada.

        Args:
            extractions: Lista de extracoes
        """
        logger.info("-" * 40)
        logger.info("Layer 3: Building process memory")

        self.memory = ProcessMemory()
        self.memory.add_extractions(extractions)

        summary = self.memory.get_summary()
        conflicts = self.memory.detect_conflicts()
        gaps = self.memory.detect_gaps()

        logger.info(f"  -> {len(summary['temas_encontrados'])} temas indexados")
        logger.info(f"  -> {len(summary['eventos_encontrados'])} tipos de evento")
        logger.info(f"  -> {len(conflicts)} conflitos detectados")
        logger.info(f"  -> {len(gaps)} lacunas identificadas")

    async def _layer4_consolidation(self) -> List[ConsolidatedTheme]:
        """
        Layer 4: Consolida temas resolvendo conflitos.

        Returns:
            Lista de ConsolidatedTheme
        """
        logger.info("-" * 40)
        logger.info("Layer 4: Semantic consolidation")

        if not self.memory:
            raise ValueError("ProcessMemory nao inicializada")

        consolidated = await self.consolidator.consolidate(self.memory)

        # Log estatisticas de status
        status_counts: Dict[str, int] = {}
        for theme in consolidated:
            status_counts[theme.status.value] = status_counts.get(theme.status.value, 0) + 1

        logger.info(f"  -> {len(consolidated)} temas consolidados")
        logger.debug(f"  Status: {status_counts}")

        return consolidated

    async def _layer5_generation(
        self,
        consolidated: List[ConsolidatedTheme]
    ) -> List[SectionResult]:
        """
        Layer 5: Gera as 9 secoes do resumo.

        Args:
            consolidated: Temas consolidados

        Returns:
            Lista de SectionResult
        """
        logger.info("-" * 40)
        logger.info("Layer 5: Section generation")

        if not self.memory:
            raise ValueError("ProcessMemory nao inicializada")

        sections = await self.generator.generate_sections(consolidated, self.memory)

        logger.info(f"  -> {len(sections)} secoes geradas")

        return sections

    async def _layer6_validation(
        self,
        sections: List[SectionResult],
        consolidated: List[ConsolidatedTheme]
    ) -> List[SectionResult]:
        """
        Layer 6: Valida secoes e regenera se necessario.

        Args:
            sections: Secoes geradas
            consolidated: Temas consolidados

        Returns:
            Secoes validadas/regeneradas
        """
        logger.info("-" * 40)
        logger.info("Layer 6: Validation")

        if not self.memory:
            raise ValueError("ProcessMemory nao inicializada")

        # Primeira validacao
        validation_results = self.validator.validate_all_sections(sections)

        # Identifica secoes para regenerar
        to_regenerate = self.validator.get_sections_to_regenerate(validation_results)

        if not to_regenerate:
            logger.info("  -> Todas as secoes passaram na validacao")
            return sections

        logger.info(f"  -> {len(to_regenerate)} secoes precisam ser regeneradas")

        # Re-gera secoes com falha
        final_sections: List[SectionResult] = []
        section_map = {s.secao: s for s in sections}

        for section_name, errors in to_regenerate:
            attempts = 1
            current_section = section_map.get(section_name)

            while attempts <= self.max_regeneration_attempts:
                logger.info(f"  Regenerando {section_name} (tentativa {attempts})")

                regenerated = await self.generator.regenerate_section(
                    section_name,
                    consolidated,
                    self.memory,
                    errors
                )

                passed, new_errors = self.validator.validate_section(regenerated)

                if passed:
                    logger.info(f"  -> {section_name} passou apos regeneracao")
                    current_section = regenerated
                    break
                else:
                    errors = [e.mensagem for e in new_errors]
                    current_section = regenerated
                    attempts += 1

            if current_section:
                current_section.tentativas = attempts
                section_map[section_name] = current_section

        # Reconstroi lista na ordem correta
        for section in sections:
            if section.secao in section_map:
                final_sections.append(section_map[section.secao])
            else:
                final_sections.append(section)

        return final_sections

    def _build_final_result(
        self,
        sections: List[SectionResult],
        total_chunks: int,
        total_extractions: int,
        temas_consolidados: int,
        elapsed_ms: float
    ) -> PipelineResult:
        """
        Constroi resultado final do pipeline.

        Args:
            sections: Secoes finais
            total_chunks: Total de chunks processados
            total_extractions: Total de extracoes
            temas_consolidados: Total de temas consolidados
            elapsed_ms: Tempo de processamento

        Returns:
            PipelineResult
        """
        # Conta conflitos
        conflitos = 0
        if self.memory:
            conflitos = len(self.memory.detect_conflicts())

        # Lista pendencias
        pendencias: List[str] = []
        if self.memory:
            for gap in self.memory.detect_gaps():
                pendencias.append(f"{gap.tema.value}: {gap.descricao}")

        # Adiciona pendencias de secoes nao validadas
        for section in sections:
            if not section.validacao_ok:
                for error in section.erros_validacao:
                    pendencias.append(f"{section.secao}: {error.mensagem}")

        return PipelineResult(
            secoes=sections,
            total_chunks=total_chunks,
            total_extracoes=total_extractions,
            temas_consolidados=temas_consolidados,
            conflitos_encontrados=conflitos,
            pendencias=pendencias,
            tempo_processamento_ms=elapsed_ms,
        )
