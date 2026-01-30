"""
Chunker juridico inteligente para o pipeline anti-alucinacao (Layer 1).

Divide documentos por unidade logica juridica (sentenca, acordao, laudo, etc)
ao inves de simplesmente por numero de palavras.
"""

import re
import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class LegalChunk:
    """Representa um chunk juridico com metadados."""
    chunk_id: str
    texto: str
    tipo_provavel: str  # tipo de documento provavel
    localizacao_inicio: str  # fls. XX ou pagina XX
    localizacao_fim: str
    palavra_count: int


class LegalChunker:
    """
    Chunker inteligente que divide documentos por unidade juridica.

    Identifica limites naturais de documentos juridicos como:
    - Sentencas
    - Acordaos
    - Laudos
    - Peticoes
    - Calculos
    - Contratos
    """

    # Padroes que indicam inicio de novo documento/secao
    DOCUMENT_START_PATTERNS: List[Tuple[str, str]] = [
        # Sentencas e decisoes
        (r"(?i)^\s*S\s*E\s*N\s*T\s*E\s*N\s*[CÇ]\s*A", "sentenca"),
        (r"(?i)^\s*VISTOS[,.]?\s*etc\.?", "sentenca"),
        (r"(?i)^\s*RELATÓRIO\s*$", "sentenca"),

        # Acordaos
        (r"(?i)^\s*A\s*C\s*[OÓ]\s*R\s*D\s*[AÃ]\s*O", "acordao"),
        (r"(?i)^\s*EMENTA\s*:", "acordao"),
        (r"(?i)^\s*V\s*O\s*T\s*O", "acordao"),

        # Laudos e pericias
        (r"(?i)^\s*LAUDO\s+PERICIAL", "laudo"),
        (r"(?i)^\s*LAUDO\s+T[EÉ]CNICO", "laudo"),
        (r"(?i)^\s*PARECER\s+T[EÉ]CNICO", "laudo"),

        # Peticoes
        (r"(?i)^\s*EXCELENT[IÍ]SSIMO", "peticao"),
        (r"(?i)^\s*AO\s+DOUTO\s+JU[IÍ]ZO", "peticao"),
        (r"(?i)^\s*PETI[CÇ][AÃ]O\s+INICIAL", "peticao_inicial"),
        (r"(?i)^\s*CONTESTA[CÇ][AÃ]O", "contestacao"),
        (r"(?i)^\s*RECURSO\s+ORDIN[AÁ]RIO", "recurso"),

        # Calculos
        (r"(?i)^\s*C[AÁ]LCULO\s+DE\s+LIQUIDA[CÇ][AÃ]O", "calculo"),
        (r"(?i)^\s*DEMONSTRATIVO\s+DE\s+C[AÁ]LCULO", "calculo"),
        (r"(?i)^\s*MEM[OÓ]RIA\s+DE\s+C[AÁ]LCULO", "calculo"),

        # Contratos
        (r"(?i)^\s*CONTRATO\s+DE\s+TRABALHO", "contrato"),
        (r"(?i)^\s*TERMO\s+DE\s+RESCIS[AÃ]O", "contrato"),

        # Atas
        (r"(?i)^\s*ATA\s+DE\s+AUDI[EÊ]NCIA", "ata_audiencia"),
        (r"(?i)^\s*TERMO\s+DE\s+AUDI[EÊ]NCIA", "ata_audiencia"),

        # Documentos trabalhistas
        (r"(?i)^\s*CTPS", "ctps"),
        (r"(?i)^\s*CARTEIRA\s+DE\s+TRABALHO", "ctps"),
        (r"(?i)^\s*HOLERITE", "holerite"),
        (r"(?i)^\s*CONTRACHEQUE", "holerite"),
        (r"(?i)^\s*DEMONSTRATIVO\s+DE\s+PAGAMENTO", "holerite"),
    ]

    # Padroes de localizacao (fls., pagina, evento)
    LOCATION_PATTERNS: List[str] = [
        r"(?i)fls?\.\s*(\d+)",
        r"(?i)fl\.\s*(\d+)",
        r"(?i)p[aá]gina\s*(\d+)",
        r"(?i)p[aá]g\.?\s*(\d+)",
        r"(?i)evento\s*(\d+)",
        r"(?i)id\.?\s*(\d+)",
    ]

    def __init__(self, max_words: int = 3000, min_words: int = 100):
        """
        Inicializa o chunker.

        Args:
            max_words: Numero maximo de palavras por chunk
            min_words: Numero minimo de palavras para criar um chunk separado
        """
        self.max_words = max_words
        self.min_words = min_words

    def chunk(self, text: str) -> List[LegalChunk]:
        """
        Divide o texto em chunks juridicos.

        Args:
            text: Texto completo do documento

        Returns:
            Lista de LegalChunk
        """
        if not text or not text.strip():
            return []

        logger.debug(f"Layer 1: Iniciando chunking juridico de {len(text)} caracteres")

        # Primeiro, tenta dividir por marcadores de documento
        chunks = self._split_by_document_markers(text)

        # Se nao encontrou marcadores, divide por paragrafos respeitando limite
        if len(chunks) <= 1:
            chunks = self._split_by_paragraphs(text)

        # Aplica limite de tamanho em chunks muito grandes
        final_chunks = self._enforce_size_limits(chunks)

        logger.info(f"Layer 1: Juridical chunking - {len(final_chunks)} chunks criados")

        return final_chunks

    def _split_by_document_markers(self, text: str) -> List[LegalChunk]:
        """
        Divide texto usando marcadores de inicio de documento.

        Args:
            text: Texto a dividir

        Returns:
            Lista de chunks
        """
        # Encontra todas as posicoes de inicio de documento
        markers: List[Tuple[int, str, str]] = []  # (posicao, tipo, match)

        lines = text.split('\n')
        current_pos = 0

        for i, line in enumerate(lines):
            for pattern, doc_type in self.DOCUMENT_START_PATTERNS:
                if re.search(pattern, line):
                    markers.append((current_pos, doc_type, line.strip()[:50]))
                    break
            current_pos += len(line) + 1  # +1 para o \n

        if not markers:
            return [self._create_chunk("chunk_0", text, "outros", "inicio", "fim")]

        # Ordena por posicao
        markers.sort(key=lambda x: x[0])

        chunks: List[LegalChunk] = []
        for i, (pos, doc_type, _) in enumerate(markers):
            # Determina fim do chunk
            if i + 1 < len(markers):
                end_pos = markers[i + 1][0]
            else:
                end_pos = len(text)

            chunk_text = text[pos:end_pos].strip()

            if len(chunk_text.split()) >= self.min_words:
                loc_inicio = self._extract_location(chunk_text[:500])
                loc_fim = self._extract_location(chunk_text[-500:])

                chunk = self._create_chunk(
                    f"chunk_{i}",
                    chunk_text,
                    doc_type,
                    loc_inicio,
                    loc_fim
                )
                chunks.append(chunk)

        return chunks

    def _split_by_paragraphs(self, text: str) -> List[LegalChunk]:
        """
        Divide texto por paragrafos, respeitando limite de palavras.

        Args:
            text: Texto a dividir

        Returns:
            Lista de chunks
        """
        paragraphs = re.split(r'\n\s*\n', text)
        chunks: List[LegalChunk] = []
        current_text: List[str] = []
        current_word_count = 0
        chunk_index = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            para_words = len(para.split())

            # Se adicionar este paragrafo excede o limite
            if current_word_count + para_words > self.max_words and current_text:
                # Finaliza chunk atual
                chunk_text = '\n\n'.join(current_text)
                tipo = self._detect_document_type(chunk_text)
                loc = self._extract_location(chunk_text)

                chunk = self._create_chunk(
                    f"chunk_{chunk_index}",
                    chunk_text,
                    tipo,
                    loc,
                    loc
                )
                chunks.append(chunk)
                chunk_index += 1

                current_text = [para]
                current_word_count = para_words
            else:
                current_text.append(para)
                current_word_count += para_words

        # Ultimo chunk
        if current_text:
            chunk_text = '\n\n'.join(current_text)
            tipo = self._detect_document_type(chunk_text)
            loc = self._extract_location(chunk_text)

            chunk = self._create_chunk(
                f"chunk_{chunk_index}",
                chunk_text,
                tipo,
                loc,
                loc
            )
            chunks.append(chunk)

        return chunks

    def _enforce_size_limits(self, chunks: List[LegalChunk]) -> List[LegalChunk]:
        """
        Garante que nenhum chunk exceda o limite de palavras.

        Args:
            chunks: Lista de chunks a verificar

        Returns:
            Lista de chunks dentro do limite
        """
        result: List[LegalChunk] = []

        for chunk in chunks:
            if chunk.palavra_count <= self.max_words:
                result.append(chunk)
            else:
                # Divide chunk grande
                sub_chunks = self._split_large_chunk(chunk)
                result.extend(sub_chunks)

        # Renumera chunk_ids
        for i, chunk in enumerate(result):
            chunk.chunk_id = f"chunk_{i}"

        return result

    def _split_large_chunk(self, chunk: LegalChunk) -> List[LegalChunk]:
        """
        Divide um chunk grande em chunks menores.

        Args:
            chunk: Chunk a dividir

        Returns:
            Lista de chunks menores
        """
        words = chunk.texto.split()
        sub_chunks: List[LegalChunk] = []

        for i in range(0, len(words), self.max_words):
            sub_text = ' '.join(words[i:i + self.max_words])
            sub_chunk = self._create_chunk(
                f"{chunk.chunk_id}_{i // self.max_words}",
                sub_text,
                chunk.tipo_provavel,
                chunk.localizacao_inicio,
                chunk.localizacao_fim
            )
            sub_chunks.append(sub_chunk)

        return sub_chunks

    def _create_chunk(
        self,
        chunk_id: str,
        texto: str,
        tipo: str,
        loc_inicio: str,
        loc_fim: str
    ) -> LegalChunk:
        """
        Cria um LegalChunk.

        Args:
            chunk_id: ID do chunk
            texto: Texto do chunk
            tipo: Tipo de documento provavel
            loc_inicio: Localizacao inicial
            loc_fim: Localizacao final

        Returns:
            LegalChunk
        """
        return LegalChunk(
            chunk_id=chunk_id,
            texto=texto,
            tipo_provavel=tipo,
            localizacao_inicio=loc_inicio,
            localizacao_fim=loc_fim,
            palavra_count=len(texto.split())
        )

    def _detect_document_type(self, text: str) -> str:
        """
        Detecta o tipo de documento a partir do texto.

        Args:
            text: Texto a analisar

        Returns:
            Tipo de documento detectado
        """
        # Verifica primeiras linhas
        first_lines = text[:1000]

        for pattern, doc_type in self.DOCUMENT_START_PATTERNS:
            if re.search(pattern, first_lines):
                return doc_type

        # Heuristicas adicionais
        text_lower = text.lower()

        if "julgo procedente" in text_lower or "julgo improcedente" in text_lower:
            return "sentenca"
        if "acordam os" in text_lower or "dou provimento" in text_lower:
            return "acordao"
        if "perito" in text_lower and "laudo" in text_lower:
            return "laudo"
        if "admissao" in text_lower and "demissao" in text_lower:
            return "ctps"
        if "liquido a receber" in text_lower or "valor bruto" in text_lower:
            return "holerite"

        return "outros"

    def _extract_location(self, text: str) -> str:
        """
        Extrai localizacao (fls., pagina, evento) do texto.

        Args:
            text: Texto onde buscar

        Returns:
            Localizacao encontrada ou "nao identificado"
        """
        for pattern in self.LOCATION_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return match.group(0)

        return "nao identificado"
