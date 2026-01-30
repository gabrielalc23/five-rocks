"""
Consolidador semantico para o pipeline anti-alucinacao (Layer 4).

Opera em modo JUIZ: compara extracoes do mesmo tema, resolve conflitos
aplicando hierarquia de fontes, e marca pendencias.
"""

import asyncio
import json
import logging
import os
import re
from typing import List, Dict, Any, Optional, Set

from openai import AsyncOpenAI, RateLimitError, APIConnectionError, APIError

from custom_types.extraction_types import (
    ChunkExtraction,
    ConsolidatedTheme,
    Tema,
    StatusConsolidacao,
    Conflict,
)
from custom_types.process_memory import ProcessMemory

logger = logging.getLogger(__name__)


# Prompt de consolidacao - modo JUIZ
CONSOLIDATION_PROMPT = """Voce e um CONSOLIDADOR SEMANTICO juridico. Opera em modo JUIZ.

REGRAS:
1. Compare extracoes do MESMO TEMA vindas de diferentes fontes
2. Identifique CONFLITOS entre valores divergentes
3. Determine STATUS:
   - "confirmed": informacao consistente entre fontes
   - "divergent": existem conflitos entre fontes
   - "pending": informacao incompleta ou ausente

4. HIERARQUIA DE FONTES (para resolver conflitos):
   sentenca > acordao > laudo > calculo > ctps > holerite > outros

5. Mantenha SEMPRE referencias as fontes (localizacoes)
6. NAO invente informacoes - use apenas o que foi extraido

ENTRADA:
Voce recebera extracoes de um tema especifico com:
- fatos_literais: frases exatas dos documentos
- parametros: valores extraidos (datas, valores, percentuais)
- localizacao: onde a informacao foi encontrada
- tipo_evento: tipo de documento fonte

SAIDA (JSON valido):
{
  "status": "confirmed | divergent | pending",
  "parametros_consolidados": {
    "campo1": "valor consolidado",
    "campo2": "valor consolidado"
  },
  "fontes": ["fls. XX", "evento YY"],
  "conflitos": [
    {
      "campo": "nome do campo",
      "valor_1": "valor da fonte 1",
      "fonte_1": "localizacao 1",
      "valor_2": "valor da fonte 2",
      "fonte_2": "localizacao 2",
      "resolucao": "explicacao da escolha"
    }
  ],
  "observacoes": "notas sobre a consolidacao"
}

IMPORTANTE:
- Se ha apenas uma fonte, status = "confirmed" (sem conflito possivel)
- Se valores sao identicos entre fontes, status = "confirmed"
- Se valores divergem, status = "divergent" e liste os conflitos
- Se faltam informacoes criticas, status = "pending"
- SEMPRE inclua as fontes/localizacoes"""


class SemanticConsolidator:
    """
    Consolidador semantico que opera em modo JUIZ (Layer 4).

    Compara extracoes do mesmo tema, resolve conflitos aplicando
    hierarquia de fontes, e identifica pendencias.
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        max_retries: int = 3,
        temperature: float = 0.1,
    ):
        """
        Inicializa o consolidador.

        Args:
            model: Modelo OpenAI a usar
            api_key: Chave da API
            max_retries: Tentativas em caso de erro
            temperature: Temperatura do modelo
        """
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.max_retries = max_retries
        self.temperature = temperature

        if not self.api_key:
            raise ValueError("API key da OpenAI nao encontrada")

        self.client = AsyncOpenAI(api_key=self.api_key)

    async def consolidate(
        self,
        memory: ProcessMemory
    ) -> List[ConsolidatedTheme]:
        """
        Consolida todos os temas encontrados na memoria.

        Args:
            memory: ProcessMemory com as extracoes

        Returns:
            Lista de temas consolidados
        """
        temas = memory.get_all_temas()
        logger.info(f"Layer 4: Semantic consolidation - {len(temas)} temas")

        consolidated: List[ConsolidatedTheme] = []

        for tema in temas:
            extractions = memory.get_by_tema(tema)
            if not extractions:
                continue

            theme_result = await self._consolidate_theme(tema, extractions, memory)
            if theme_result:
                consolidated.append(theme_result)

        logger.info(f"Layer 4: {len(consolidated)} temas consolidados")
        return consolidated

    async def _consolidate_theme(
        self,
        tema: Tema,
        extractions: List[ChunkExtraction],
        memory: ProcessMemory
    ) -> Optional[ConsolidatedTheme]:
        """
        Consolida um tema especifico.

        Args:
            tema: Tema a consolidar
            extractions: Extracoes do tema
            memory: ProcessMemory para contexto adicional

        Returns:
            ConsolidatedTheme ou None
        """
        # Se ha apenas uma extracao, confirma diretamente
        if len(extractions) == 1:
            return self._create_single_source_consolidation(tema, extractions[0])

        # Multiplas extracoes - precisa consolidar
        for attempt in range(self.max_retries):
            try:
                return await self._call_consolidation_api(tema, extractions, memory)
            except (RateLimitError, APIConnectionError) as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"Falha na consolidacao de {tema.value}: {e}")
                    return self._create_fallback_consolidation(tema, extractions, memory)
                wait_time = (2 ** attempt) + (attempt * 0.5)
                await asyncio.sleep(wait_time)
            except Exception as e:
                logger.error(f"Erro na consolidacao de {tema.value}: {e}")
                return self._create_fallback_consolidation(tema, extractions, memory)

        return None

    async def _call_consolidation_api(
        self,
        tema: Tema,
        extractions: List[ChunkExtraction],
        memory: ProcessMemory
    ) -> Optional[ConsolidatedTheme]:
        """
        Chama a API para consolidar um tema.

        Args:
            tema: Tema a consolidar
            extractions: Extracoes do tema
            memory: ProcessMemory

        Returns:
            ConsolidatedTheme ou None
        """
        # Prepara dados das extracoes para o prompt
        extractions_text = self._format_extractions_for_prompt(extractions)

        # Detecta conflitos conhecidos
        known_conflicts = [c for c in memory.detect_conflicts() if c.tema == tema]

        context = f"""TEMA: {tema.value}

EXTRACOES ENCONTRADAS ({len(extractions)} fontes):
{extractions_text}

CONFLITOS JA DETECTADOS: {len(known_conflicts)}
{self._format_conflicts_for_prompt(known_conflicts) if known_conflicts else "Nenhum conflito detectado automaticamente"}

Consolide as informacoes acima seguindo a hierarquia de fontes."""

        request_params: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": CONSOLIDATION_PROMPT},
                {"role": "user", "content": context},
            ],
            "temperature": self.temperature,
            "max_tokens": 1500,
        }

        if "gpt-4o" in self.model or "gpt-4-turbo" in self.model:
            request_params["response_format"] = {"type": "json_object"}

        response = await self.client.chat.completions.create(**request_params)

        content = response.choices[0].message.content
        if not content:
            return None

        return self._parse_consolidation_response(content, tema, extractions)

    def _format_extractions_for_prompt(
        self,
        extractions: List[ChunkExtraction]
    ) -> str:
        """
        Formata extracoes para o prompt.

        Args:
            extractions: Lista de extracoes

        Returns:
            String formatada
        """
        parts: List[str] = []

        for i, ext in enumerate(extractions, 1):
            part = f"""
--- FONTE {i}: {ext.tipo_evento.value} ({ext.localizacao}) ---
Fatos literais:
{chr(10).join('- ' + f for f in ext.fatos_literais[:5])}

Parametros:
{json.dumps(ext.parametros, ensure_ascii=False, indent=2)}
"""
            parts.append(part)

        return "\n".join(parts)

    def _format_conflicts_for_prompt(self, conflicts: List[Conflict]) -> str:
        """
        Formata conflitos para o prompt.

        Args:
            conflicts: Lista de conflitos

        Returns:
            String formatada
        """
        parts: List[str] = []

        for c in conflicts:
            parts.append(
                f"- {c.campo}: '{c.valor_1}' ({c.fonte_1}) vs '{c.valor_2}' ({c.fonte_2})"
            )

        return "\n".join(parts)

    def _parse_consolidation_response(
        self,
        response: str,
        tema: Tema,
        extractions: List[ChunkExtraction]
    ) -> Optional[ConsolidatedTheme]:
        """
        Parseia resposta da API em ConsolidatedTheme.

        Args:
            response: Resposta JSON da API
            tema: Tema consolidado
            extractions: Extracoes originais

        Returns:
            ConsolidatedTheme ou None
        """
        try:
            data = self._extract_json(response)
            if not data:
                return None

            # Converte status
            status_str = data.get("status", "pending")
            try:
                status = StatusConsolidacao(status_str)
            except ValueError:
                status = StatusConsolidacao.PENDING

            # Converte conflitos
            conflitos: List[Conflict] = []
            for c_data in data.get("conflitos", []):
                conflito = Conflict(
                    tema=tema,
                    campo=c_data.get("campo", ""),
                    valor_1=c_data.get("valor_1"),
                    fonte_1=c_data.get("fonte_1", ""),
                    valor_2=c_data.get("valor_2"),
                    fonte_2=c_data.get("fonte_2", ""),
                    resolucao=c_data.get("resolucao"),
                )
                conflitos.append(conflito)

            # Garante que temos fontes
            fontes = data.get("fontes", [])
            if not fontes:
                fontes = [ext.localizacao for ext in extractions]

            return ConsolidatedTheme(
                tema=tema,
                status=status,
                parametros_consolidados=data.get("parametros_consolidados", {}),
                fontes=fontes,
                conflitos=conflitos,
                observacoes=data.get("observacoes", ""),
            )

        except Exception as e:
            logger.error(f"Erro ao parsear consolidacao: {e}")
            return None

    def _create_single_source_consolidation(
        self,
        tema: Tema,
        extraction: ChunkExtraction
    ) -> ConsolidatedTheme:
        """
        Cria consolidacao para tema com fonte unica.

        Args:
            tema: Tema
            extraction: Unica extracao

        Returns:
            ConsolidatedTheme confirmado
        """
        return ConsolidatedTheme(
            tema=tema,
            status=StatusConsolidacao.CONFIRMED,
            parametros_consolidados=extraction.parametros,
            fontes=[extraction.localizacao],
            conflitos=[],
            observacoes="Fonte unica - sem conflitos possiveis",
        )

    def _create_fallback_consolidation(
        self,
        tema: Tema,
        extractions: List[ChunkExtraction],
        memory: ProcessMemory
    ) -> ConsolidatedTheme:
        """
        Cria consolidacao fallback quando API falha.

        Usa logica simples de prioridade sem GPT.

        Args:
            tema: Tema
            extractions: Extracoes
            memory: ProcessMemory

        Returns:
            ConsolidatedTheme
        """
        # Usa parametros consolidados da memoria (que aplica prioridade)
        parametros = memory.get_parametros_by_tema(tema)
        fontes = memory.get_fontes_by_tema(tema)
        conflitos = [c for c in memory.detect_conflicts() if c.tema == tema]

        # Determina status
        if conflitos:
            status = StatusConsolidacao.DIVERGENT
        elif parametros:
            status = StatusConsolidacao.CONFIRMED
        else:
            status = StatusConsolidacao.PENDING

        return ConsolidatedTheme(
            tema=tema,
            status=status,
            parametros_consolidados=parametros,
            fontes=fontes,
            conflitos=conflitos,
            observacoes="Consolidacao automatica (fallback)",
        )

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Extrai JSON de uma string.

        Args:
            text: Texto que pode conter JSON

        Returns:
            Dicionario ou None
        """
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        return None
