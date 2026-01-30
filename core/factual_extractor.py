"""
Extrator factual para o pipeline anti-alucinacao (Layer 2).

Opera em modo ROBO: extrai APENAS o que esta ESCRITO no documento,
sem interpretacoes ou inferencias.
"""

import asyncio
import json
import logging
import os
import re
from typing import List, Dict, Any, Optional

from openai import AsyncOpenAI, RateLimitError, APIConnectionError, APIError

from custom_types.extraction_types import (
    ChunkExtraction,
    TipoEvento,
    Tema,
)
from utils.legal_chunker import LegalChunk

logger = logging.getLogger(__name__)


# Prompt de extracao factual - modo ROBO
EXTRACTION_PROMPT = """Voce e um EXTRATOR FACTUAL de documentos juridicos. Opera em modo ROBO.

REGRAS ABSOLUTAS:
1. NAO interprete - extraia APENAS o que esta ESCRITO
2. NAO complete lacunas - se nao existe, NAO inclua
3. Copie valores EXATAMENTE como aparecem (numeros, datas, percentuais)
4. TODA informacao DEVE ter localizacao (fls/pagina/evento)
5. Se nao encontrar informacao, NAO invente - deixe vazio ou omita
6. Preserve terminologia juridica exata
7. Extraia fatos LITERAIS - copie frases do documento

TIPOS DE EVENTO (escolha UM):
- sentenca, acordao, laudo, ctps, holerite, peticao_inicial, contestacao
- recurso, despacho, calculo, contrato, documento_pessoal, ata_audiencia
- procuracao, outros

TEMAS POSSIVEIS (escolha todos aplicaveis):
- jornada, horas_extras, adicional_noturno, fgts, multa_fgts
- ferias, decimo_terceiro, aviso_previo, verbas_rescisorias
- danos_morais, danos_materiais, salario, remuneracao
- vinculo_empregaticio, intervalo_intrajornada, intervalo_interjornada
- dsr, adicional_insalubridade, adicional_periculosidade
- equiparacao_salarial, desvio_funcao, acumulo_funcao
- estabilidade, reintegracao, vale_transporte, vale_alimentacao
- plr, honorarios, custas, juros, correcao_monetaria
- compensacao, prescricao, outros

Responda APENAS com JSON valido no formato:
{
  "tipo_evento": "tipo escolhido",
  "temas": ["tema1", "tema2"],
  "fatos_literais": [
    "Frase EXATA copiada do documento 1",
    "Frase EXATA copiada do documento 2"
  ],
  "parametros": {
    "data_admissao": "valor exato",
    "data_demissao": "valor exato",
    "salario": "valor exato",
    "percentual_horas_extras": "valor exato",
    "jornada": "descricao exata",
    "valor_condenacao": "valor exato",
    "outros_parametros": "conforme documento"
  },
  "localizacao": "fls. XX / pagina XX / evento XX"
}

IMPORTANTE:
- Extraia SOMENTE informacoes presentes no texto
- Se o campo nao existe no documento, OMITA do JSON
- Fatos literais devem ser COPIAS do texto, nao resumos"""


class FactualExtractor:
    """
    Extrator factual que opera em modo ROBO (Layer 2).

    Extrai informacoes de forma literal, sem interpretacoes,
    preservando localizacoes e valores exatos.
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        max_retries: int = 3,
        max_parallel: int = 3,
        temperature: float = 0.0,
    ):
        """
        Inicializa o extrator.

        Args:
            model: Modelo OpenAI a usar
            api_key: Chave da API (ou usa env var)
            max_retries: Tentativas em caso de erro
            max_parallel: Extracoes paralelas maximas
            temperature: Temperatura do modelo (0 = deterministico)
        """
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.max_retries = max_retries
        self.max_parallel = max_parallel
        self.temperature = temperature

        if not self.api_key:
            raise ValueError("API key da OpenAI nao encontrada")

        self.client = AsyncOpenAI(api_key=self.api_key)

    async def extract_from_chunks(
        self,
        chunks: List[LegalChunk]
    ) -> List[ChunkExtraction]:
        """
        Extrai informacoes de multiplos chunks em paralelo.

        Args:
            chunks: Lista de chunks juridicos

        Returns:
            Lista de extracoes
        """
        logger.info(f"Layer 2: Factual extraction - {len(chunks)} chunks")

        semaphore = asyncio.Semaphore(self.max_parallel)

        async def extract_with_semaphore(chunk: LegalChunk) -> Optional[ChunkExtraction]:
            async with semaphore:
                return await self._extract_from_chunk(chunk)

        tasks = [extract_with_semaphore(chunk) for chunk in chunks]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        extractions: List[ChunkExtraction] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Erro na extracao do chunk {i}: {result}")
            elif result is not None:
                extractions.append(result)

        logger.info(f"Layer 2: {len(extractions)} extracoes bem-sucedidas")
        return extractions

    async def _extract_from_chunk(
        self,
        chunk: LegalChunk
    ) -> Optional[ChunkExtraction]:
        """
        Extrai informacoes de um unico chunk.

        Args:
            chunk: Chunk juridico

        Returns:
            ChunkExtraction ou None se falhar
        """
        for attempt in range(self.max_retries):
            try:
                return await self._call_extraction_api(chunk)
            except (RateLimitError, APIConnectionError) as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"Falha apos {self.max_retries} tentativas: {e}")
                    return None
                wait_time = (2 ** attempt) + (attempt * 0.5)
                logger.warning(f"Tentativa {attempt + 1} falhou, aguardando {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
            except APIError as e:
                logger.error(f"Erro na API: {e}")
                return None
            except Exception as e:
                logger.error(f"Erro inesperado na extracao: {e}")
                return None

        return None

    async def _call_extraction_api(
        self,
        chunk: LegalChunk
    ) -> Optional[ChunkExtraction]:
        """
        Chama a API para extrair informacoes do chunk.

        Args:
            chunk: Chunk a processar

        Returns:
            ChunkExtraction ou None
        """
        # Adiciona contexto de localizacao ao prompt
        context_prompt = f"""CONTEXTO DO TRECHO:
- Tipo de documento provavel: {chunk.tipo_provavel}
- Localizacao no documento: {chunk.localizacao_inicio}
- Tamanho: {chunk.palavra_count} palavras

TEXTO PARA EXTRAIR:
{chunk.texto}"""

        request_params: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": context_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": 2000,
        }

        # Usa JSON mode se modelo suporta
        if "gpt-4o" in self.model or "gpt-4-turbo" in self.model:
            request_params["response_format"] = {"type": "json_object"}

        response = await self.client.chat.completions.create(**request_params)

        content = response.choices[0].message.content
        if not content:
            return None

        return self._parse_extraction_response(content, chunk)

    def _parse_extraction_response(
        self,
        response: str,
        chunk: LegalChunk
    ) -> Optional[ChunkExtraction]:
        """
        Parseia a resposta da API em ChunkExtraction.

        Args:
            response: Resposta JSON da API
            chunk: Chunk original

        Returns:
            ChunkExtraction ou None
        """
        try:
            # Tenta extrair JSON da resposta
            data = self._extract_json(response)

            if not data:
                logger.warning(f"Resposta sem JSON valido para chunk {chunk.chunk_id}")
                return None

            # Converte tipo_evento
            tipo_str = data.get("tipo_evento", chunk.tipo_provavel)
            try:
                tipo_evento = TipoEvento(tipo_str)
            except ValueError:
                tipo_evento = TipoEvento.OUTROS

            # Converte temas
            temas: List[Tema] = []
            for tema_str in data.get("temas", []):
                try:
                    temas.append(Tema(tema_str))
                except ValueError:
                    temas.append(Tema.OUTROS)

            if not temas:
                temas = [Tema.OUTROS]

            # Extrai localizacao
            localizacao = data.get("localizacao", chunk.localizacao_inicio)
            if not localizacao or localizacao == "nao informado":
                localizacao = chunk.localizacao_inicio

            return ChunkExtraction(
                chunk_id=chunk.chunk_id,
                tipo_evento=tipo_evento,
                temas=temas,
                fatos_literais=data.get("fatos_literais", []),
                parametros=data.get("parametros", {}),
                localizacao=localizacao,
                texto_original=chunk.texto,
                confianca=self._calculate_confidence(data),
            )

        except json.JSONDecodeError as e:
            logger.error(f"Erro ao parsear JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Erro ao processar resposta: {e}")
            return None

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Extrai JSON de uma string, mesmo se houver texto adicional.

        Args:
            text: Texto que pode conter JSON

        Returns:
            Dicionario ou None
        """
        # Tenta parsear diretamente
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Tenta encontrar JSON na string
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        return None

    def _calculate_confidence(self, data: Dict[str, Any]) -> float:
        """
        Calcula confianca da extracao baseado em completude.

        Args:
            data: Dados extraidos

        Returns:
            Score de confianca 0-1
        """
        score = 0.5  # Base

        # Bonus por ter fatos literais
        if data.get("fatos_literais"):
            score += 0.2

        # Bonus por ter parametros
        if data.get("parametros"):
            score += 0.15

        # Bonus por ter localizacao valida
        loc = data.get("localizacao", "")
        if loc and loc != "nao informado" and loc != "nao identificado":
            score += 0.15

        return min(1.0, score)
