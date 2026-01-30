"""
Gerador de secoes para o pipeline anti-alucinacao (Layer 5).

Opera em modo REDATOR: gera as 9 secoes do resumo final usando
dados consolidados, mantendo rastreabilidade de fontes.
"""

import asyncio
import json
import logging
import os
import re
from typing import List, Dict, Any, Optional

from openai import AsyncOpenAI, RateLimitError, APIConnectionError, APIError

from custom_types.extraction_types import (
    ConsolidatedTheme,
    SectionResult,
    StatusConsolidacao,
)
from custom_types.process_memory import ProcessMemory

logger = logging.getLogger(__name__)


# Prompts para cada secao - modo REDATOR
SECTION_PROMPTS: Dict[str, str] = {
    "cabecalho": """Gere o CABECALHO do resumo processual.

DEVE CONTER (se disponivel):
- numero_processo: numero completo do processo
- tribunal: tribunal/vara
- partes: autor e reu
- tipo_acao: tipo de acao trabalhista
- data_distribuicao: data de ajuizamento
- fase_atual: fase processual atual

REGRAS:
- Use APENAS informacoes dos dados consolidados
- Inclua a fonte/localizacao de cada informacao
- Se nao houver informacao, use "nao identificado"

Responda em JSON:
{
  "numero_processo": {"valor": "xxx", "fonte": "fls. XX"},
  "tribunal": {"valor": "xxx", "fonte": "fls. XX"},
  "partes": {
    "autor": {"valor": "xxx", "fonte": "fls. XX"},
    "reu": {"valor": "xxx", "fonte": "fls. XX"}
  },
  "tipo_acao": {"valor": "xxx", "fonte": "fls. XX"},
  "data_distribuicao": {"valor": "xxx", "fonte": "fls. XX"},
  "fase_atual": {"valor": "xxx", "fonte": "fls. XX"}
}""",

    "timeline": """Gere a TIMELINE do processo.

DEVE CONTER:
- Lista cronologica de eventos importantes
- Data de cada evento
- Descricao breve
- Fonte/localizacao

EVENTOS IMPORTANTES:
- Distribuicao
- Contestacao
- Audiencias
- Pericias/laudos
- Sentenca
- Recursos
- Acordao

Responda em JSON:
{
  "eventos": [
    {
      "data": "DD/MM/AAAA",
      "evento": "descricao",
      "fonte": "fls. XX"
    }
  ]
}""",

    "resultado_por_pedido": """Gere o RESULTADO POR PEDIDO.

PARA CADA PEDIDO listado nos dados:
- pedido: descricao do pedido
- resultado: procedente / improcedente / parcialmente procedente
- fundamentacao: razao da decisao (resumida)
- valor: valor deferido (se aplicavel)
- fonte: localizacao da decisao

REGRAS:
- Liste TODOS os pedidos identificados
- Inclua resultado de cada um
- Cite a fonte da decisao

Responda em JSON:
{
  "pedidos": [
    {
      "pedido": "descricao",
      "resultado": "procedente/improcedente/parcial",
      "fundamentacao": "razao resumida",
      "valor": "R$ XX,XX ou N/A",
      "fonte": "fls. XX"
    }
  ]
}""",

    "parametros_calculo": """Gere os PARAMETROS DE CALCULO.

DEVE CONTER:
- salario_base: valor e fonte
- periodo_contratual: datas de admissao e demissao
- jornada: horario de trabalho
- percentuais: horas extras, adicionais, etc.
- indices: correcao monetaria, juros
- bases_de_calculo: para cada verba

REGRAS:
- TODOS os valores devem ter fonte
- Percentuais exatos como aparecem no documento
- Datas no formato DD/MM/AAAA

Responda em JSON:
{
  "salario_base": {"valor": "R$ XX", "fonte": "fls. XX"},
  "periodo_contratual": {
    "admissao": {"valor": "DD/MM/AAAA", "fonte": "fls. XX"},
    "demissao": {"valor": "DD/MM/AAAA", "fonte": "fls. XX"}
  },
  "jornada": {"valor": "descricao", "fonte": "fls. XX"},
  "percentuais": {
    "horas_extras": {"valor": "XX%", "fonte": "fls. XX"},
    "adicional_noturno": {"valor": "XX%", "fonte": "fls. XX"}
  },
  "indices": {
    "correcao_monetaria": {"valor": "indice", "fonte": "fls. XX"},
    "juros": {"valor": "XX%", "fonte": "fls. XX"}
  }
}""",

    "documentos_chave": """Liste os DOCUMENTOS CHAVE do processo.

DEVE CONTER:
- Documentos mais relevantes para o caso
- Tipo de documento
- Localizacao (fls./evento)
- Relevancia para o caso

TIPOS IMPORTANTES:
- Sentenca
- Acordao
- Laudos periciais
- CTPS
- Contracheques
- Contrato de trabalho
- Calculos de liquidacao

Responda em JSON:
{
  "documentos": [
    {
      "tipo": "tipo do documento",
      "localizacao": "fls. XX",
      "relevancia": "importancia para o caso"
    }
  ]
}""",

    "pendencias": """Liste as PENDENCIAS identificadas.

DEVE CONTER:
- Informacoes faltantes
- Conflitos nao resolvidos
- Documentos necessarios
- Calculos pendentes

CATEGORIAS:
- critica: impede calculo/execucao
- importante: afeta valores
- informativa: complementar

Responda em JSON:
{
  "pendencias": [
    {
      "descricao": "o que falta",
      "categoria": "critica/importante/informativa",
      "impacto": "como afeta o caso"
    }
  ]
}""",

    "proximos_passos": """Liste os PROXIMOS PASSOS recomendados.

BASEADO NA FASE ATUAL:
- Acoes necessarias
- Prazos se identificados
- Documentos a providenciar
- Calculos a realizar

FASES COMUNS:
- Liquidacao: calcular valores
- Execucao: citar para pagamento
- Recurso: interpor/contrarrazoar
- Transito em julgado: iniciar execucao

Responda em JSON:
{
  "proximos_passos": [
    {
      "acao": "descricao da acao",
      "prazo": "prazo se houver",
      "responsavel": "quem deve fazer"
    }
  ]
}""",

    "insight": """Gere INSIGHTS sobre o caso.

ANALISE:
- Pontos fortes do caso
- Pontos fracos/riscos
- Valores potenciais
- Complexidade

IMPORTANTE:
- Base apenas nos fatos extraidos
- Nao especule alem dos dados
- Cite fontes quando possivel

Responda em JSON:
{
  "pontos_fortes": ["ponto 1", "ponto 2"],
  "pontos_fracos": ["risco 1", "risco 2"],
  "valor_estimado": {
    "minimo": "R$ XX",
    "maximo": "R$ XX",
    "base_calculo": "explicacao"
  },
  "complexidade": "baixa/media/alta",
  "observacoes": "notas adicionais"
}""",

    "resumo": """Gere o RESUMO EXECUTIVO do caso.

DEVE CONTER:
- Sintese do caso em 3-5 paragrafos
- Principais pontos decididos
- Valores envolvidos
- Situacao atual

ESTRUTURA:
1. Contexto (partes, tipo de acao)
2. Principais pedidos e resultados
3. Valores deferidos
4. Situacao atual e proximos passos

REGRAS:
- Linguagem clara e objetiva
- Fatos principais apenas
- Sem repeticao de detalhes

Responda em JSON:
{
  "resumo_executivo": "texto do resumo",
  "principais_verbas": [
    {"verba": "nome", "valor": "R$ XX", "status": "deferido/indeferido"}
  ],
  "valor_total_estimado": "R$ XX",
  "situacao_atual": "descricao"
}"""
}


class SectionGenerator:
    """
    Gerador de secoes que opera em modo REDATOR (Layer 5).

    Gera as 9 secoes do resumo final usando dados consolidados,
    mantendo rastreabilidade de fontes.
    """

    # Ordem das secoes para geracao
    SECTION_ORDER: List[str] = [
        "cabecalho",
        "timeline",
        "resultado_por_pedido",
        "parametros_calculo",
        "documentos_chave",
        "pendencias",
        "proximos_passos",
        "insight",
        "resumo",
    ]

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        max_retries: int = 3,
        temperature: float = 0.2,
    ):
        """
        Inicializa o gerador.

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

    async def generate_sections(
        self,
        consolidated_themes: List[ConsolidatedTheme],
        memory: ProcessMemory
    ) -> List[SectionResult]:
        """
        Gera todas as secoes do resumo.

        Args:
            consolidated_themes: Temas consolidados
            memory: ProcessMemory com extracoes

        Returns:
            Lista de SectionResult
        """
        logger.info(f"Layer 5: Section generation - {len(self.SECTION_ORDER)} secoes")

        sections: List[SectionResult] = []

        for section_name in self.SECTION_ORDER:
            result = await self._generate_section(
                section_name,
                consolidated_themes,
                memory
            )
            sections.append(result)

        logger.info(f"Layer 5: {len(sections)} secoes geradas")
        return sections

    async def regenerate_section(
        self,
        section_name: str,
        consolidated_themes: List[ConsolidatedTheme],
        memory: ProcessMemory,
        previous_errors: List[str]
    ) -> SectionResult:
        """
        Regenera uma secao especifica apos falha de validacao.

        Args:
            section_name: Nome da secao
            consolidated_themes: Temas consolidados
            memory: ProcessMemory
            previous_errors: Erros da tentativa anterior

        Returns:
            SectionResult regenerado
        """
        logger.info(f"Layer 5: Regenerando secao {section_name}")

        return await self._generate_section(
            section_name,
            consolidated_themes,
            memory,
            error_context=previous_errors
        )

    async def _generate_section(
        self,
        section_name: str,
        consolidated_themes: List[ConsolidatedTheme],
        memory: ProcessMemory,
        error_context: Optional[List[str]] = None
    ) -> SectionResult:
        """
        Gera uma secao especifica.

        Args:
            section_name: Nome da secao
            consolidated_themes: Temas consolidados
            memory: ProcessMemory
            error_context: Erros anteriores para correcao

        Returns:
            SectionResult
        """
        for attempt in range(self.max_retries):
            try:
                content = await self._call_generation_api(
                    section_name,
                    consolidated_themes,
                    memory,
                    error_context
                )

                if content:
                    fontes = self._extract_sources_from_content(content)
                    return SectionResult(
                        secao=section_name,
                        conteudo=content,
                        fontes_utilizadas=fontes,
                        validacao_ok=True,
                        tentativas=attempt + 1,
                    )

            except (RateLimitError, APIConnectionError) as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"Falha na geracao de {section_name}: {e}")
                    break
                wait_time = (2 ** attempt) + (attempt * 0.5)
                await asyncio.sleep(wait_time)
            except Exception as e:
                logger.error(f"Erro na geracao de {section_name}: {e}")
                break

        # Fallback: retorna secao vazia marcada como falha
        return SectionResult(
            secao=section_name,
            conteudo={"erro": "Falha na geracao"},
            fontes_utilizadas=[],
            validacao_ok=False,
            tentativas=self.max_retries,
        )

    async def _call_generation_api(
        self,
        section_name: str,
        consolidated_themes: List[ConsolidatedTheme],
        memory: ProcessMemory,
        error_context: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Chama a API para gerar uma secao.

        Args:
            section_name: Nome da secao
            consolidated_themes: Temas consolidados
            memory: ProcessMemory
            error_context: Erros anteriores

        Returns:
            Conteudo da secao ou None
        """
        section_prompt = SECTION_PROMPTS.get(section_name, "")
        if not section_prompt:
            logger.warning(f"Prompt nao encontrado para secao: {section_name}")
            return None

        # Prepara dados consolidados
        themes_data = self._format_themes_for_prompt(consolidated_themes)

        # Prepara contexto adicional da memoria
        memory_context = self._format_memory_context(memory)

        context = f"""DADOS CONSOLIDADOS:
{themes_data}

CONTEXTO ADICIONAL:
{memory_context}"""

        # Adiciona contexto de erro se for regeneracao
        if error_context:
            context += f"""

ATENCAO - ERROS NA TENTATIVA ANTERIOR:
{chr(10).join('- ' + e for e in error_context)}

Corrija estes problemas nesta geracao."""

        request_params: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": section_prompt},
                {"role": "user", "content": context},
            ],
            "temperature": self.temperature,
            "max_tokens": 2000,
        }

        if "gpt-4o" in self.model or "gpt-4-turbo" in self.model:
            request_params["response_format"] = {"type": "json_object"}

        response = await self.client.chat.completions.create(**request_params)

        content = response.choices[0].message.content
        if not content:
            return None

        return self._extract_json(content)

    def _format_themes_for_prompt(
        self,
        themes: List[ConsolidatedTheme]
    ) -> str:
        """
        Formata temas consolidados para o prompt.

        Args:
            themes: Lista de temas consolidados

        Returns:
            String formatada
        """
        parts: List[str] = []

        for theme in themes:
            status_emoji = {
                StatusConsolidacao.CONFIRMED: "[OK]",
                StatusConsolidacao.DIVERGENT: "[!]",
                StatusConsolidacao.PENDING: "[?]",
            }.get(theme.status, "")

            part = f"""
TEMA: {theme.tema.value} {status_emoji}
Status: {theme.status.value}
Fontes: {', '.join(theme.fontes)}
Parametros: {json.dumps(theme.parametros_consolidados, ensure_ascii=False)}
Conflitos: {len(theme.conflitos)}
Observacoes: {theme.observacoes}"""
            parts.append(part)

        return "\n".join(parts)

    def _format_memory_context(self, memory: ProcessMemory) -> str:
        """
        Formata contexto da memoria para o prompt.

        Args:
            memory: ProcessMemory

        Returns:
            String formatada
        """
        summary = memory.get_summary()
        gaps = memory.detect_gaps()

        return f"""Total de extracoes: {summary['total_extractions']}
Temas encontrados: {len(summary['temas_encontrados'])}
Eventos encontrados: {len(summary['eventos_encontrados'])}
Lacunas detectadas: {len(gaps)}"""

    def _extract_sources_from_content(
        self,
        content: Dict[str, Any]
    ) -> List[str]:
        """
        Extrai fontes/localizacoes do conteudo gerado.

        Args:
            content: Conteudo da secao

        Returns:
            Lista de fontes
        """
        sources: List[str] = []

        def extract_recursive(obj: Any) -> None:
            if isinstance(obj, dict):
                if "fonte" in obj:
                    fonte = obj["fonte"]
                    if fonte and fonte not in sources:
                        sources.append(fonte)
                for value in obj.values():
                    extract_recursive(value)
            elif isinstance(obj, list):
                for item in obj:
                    extract_recursive(item)

        extract_recursive(content)
        return sources

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
