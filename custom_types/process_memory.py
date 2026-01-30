"""
Memoria de processo para o pipeline anti-alucinacao.

Armazena e indexa todas as extracoes de um documento, permitindo
busca por tema, evento e deteccao de conflitos/lacunas.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Any

from custom_types.extraction_types import (
    ChunkExtraction,
    Tema,
    TipoEvento,
    Conflict,
    Gap,
    ValidationSeverity,
)


@dataclass
class ProcessMemory:
    """
    Memoria de processo que armazena todas as extracoes (Layer 3).

    Indexa extracoes por tema e tipo de evento para facilitar
    a consolidacao e deteccao de conflitos.
    """
    extractions: List[ChunkExtraction] = field(default_factory=list)
    by_tema: Dict[str, List[ChunkExtraction]] = field(default_factory=lambda: defaultdict(list))
    by_evento: Dict[str, List[ChunkExtraction]] = field(default_factory=lambda: defaultdict(list))
    _parametros_index: Dict[str, Dict[str, List[tuple]]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(list)))

    def add_extraction(self, extraction: ChunkExtraction) -> None:
        """
        Adiciona uma extracao a memoria e atualiza os indices.

        Args:
            extraction: Extracao a ser adicionada
        """
        self.extractions.append(extraction)

        # Indexa por tema
        for tema in extraction.temas:
            self.by_tema[tema.value].append(extraction)

        # Indexa por tipo de evento
        self.by_evento[extraction.tipo_evento.value].append(extraction)

        # Indexa parametros para deteccao de conflitos
        for tema in extraction.temas:
            for param_key, param_value in extraction.parametros.items():
                self._parametros_index[tema.value][param_key].append(
                    (param_value, extraction.localizacao, extraction.tipo_evento)
                )

    def add_extractions(self, extractions: List[ChunkExtraction]) -> None:
        """
        Adiciona multiplas extracoes a memoria.

        Args:
            extractions: Lista de extracoes a serem adicionadas
        """
        for extraction in extractions:
            self.add_extraction(extraction)

    def get_by_tema(self, tema: Tema) -> List[ChunkExtraction]:
        """
        Retorna todas as extracoes de um tema especifico.

        Args:
            tema: Tema a buscar

        Returns:
            Lista de extracoes do tema
        """
        return self.by_tema.get(tema.value, [])

    def get_by_evento(self, tipo_evento: TipoEvento) -> List[ChunkExtraction]:
        """
        Retorna todas as extracoes de um tipo de evento.

        Args:
            tipo_evento: Tipo de evento a buscar

        Returns:
            Lista de extracoes do tipo de evento
        """
        return self.by_evento.get(tipo_evento.value, [])

    def get_all_temas(self) -> Set[Tema]:
        """
        Retorna todos os temas encontrados nas extracoes.

        Returns:
            Conjunto de temas unicos
        """
        temas: Set[Tema] = set()
        for extraction in self.extractions:
            temas.update(extraction.temas)
        return temas

    def get_all_eventos(self) -> Set[TipoEvento]:
        """
        Retorna todos os tipos de eventos encontrados.

        Returns:
            Conjunto de tipos de eventos unicos
        """
        return {extraction.tipo_evento for extraction in self.extractions}

    def detect_conflicts(self) -> List[Conflict]:
        """
        Detecta conflitos entre extracoes do mesmo tema.

        Compara valores de parametros entre diferentes extracoes
        e identifica divergencias.

        Returns:
            Lista de conflitos detectados
        """
        conflicts: List[Conflict] = []

        for tema_str, params in self._parametros_index.items():
            tema = Tema(tema_str)

            for param_key, values in params.items():
                if len(values) < 2:
                    continue

                # Agrupa valores unicos
                unique_values: Dict[str, List[tuple]] = defaultdict(list)
                for value, loc, evento in values:
                    # Normaliza valor para comparacao
                    normalized = self._normalize_value(value)
                    unique_values[normalized].append((value, loc, evento))

                # Se houver mais de um valor unico, temos conflito
                if len(unique_values) > 1:
                    sorted_values = sorted(
                        unique_values.items(),
                        key=lambda x: self._get_priority(x[1][0][2])
                    )

                    # Cria conflito entre o valor mais confiavel e os outros
                    primary = sorted_values[0][1][0]  # (value, loc, evento)

                    for i in range(1, len(sorted_values)):
                        secondary = sorted_values[i][1][0]

                        conflict = Conflict(
                            tema=tema,
                            campo=param_key,
                            valor_1=primary[0],
                            fonte_1=primary[1],
                            valor_2=secondary[0],
                            fonte_2=secondary[1],
                            resolucao=f"Preferencia: {primary[2].value} > {secondary[2].value}",
                            fonte_escolhida=primary[1],
                        )
                        conflicts.append(conflict)

        return conflicts

    def detect_gaps(self) -> List[Gap]:
        """
        Detecta lacunas de informacao nos dados extraidos.

        Verifica campos esperados por tema e identifica
        informacoes ausentes.

        Returns:
            Lista de lacunas detectadas
        """
        gaps: List[Gap] = []

        # Campos esperados por tema
        expected_fields: Dict[str, List[tuple]] = {
            Tema.HORAS_EXTRAS.value: [
                ("percentual", "Percentual de horas extras", ValidationSeverity.ERROR),
                ("periodo", "Periodo de apuracao", ValidationSeverity.WARNING),
            ],
            Tema.JORNADA.value: [
                ("horario_entrada", "Horario de entrada", ValidationSeverity.WARNING),
                ("horario_saida", "Horario de saida", ValidationSeverity.WARNING),
            ],
            Tema.FGTS.value: [
                ("percentual", "Percentual do FGTS", ValidationSeverity.WARNING),
                ("periodo", "Periodo de deposito", ValidationSeverity.WARNING),
            ],
            Tema.ADICIONAL_NOTURNO.value: [
                ("percentual", "Percentual do adicional noturno", ValidationSeverity.ERROR),
            ],
            Tema.SALARIO.value: [
                ("valor", "Valor do salario", ValidationSeverity.ERROR),
            ],
            Tema.VINCULO_EMPREGATICIO.value: [
                ("data_admissao", "Data de admissao", ValidationSeverity.ERROR),
                ("data_demissao", "Data de demissao", ValidationSeverity.WARNING),
            ],
        }

        for tema_str, fields in expected_fields.items():
            if tema_str not in self._parametros_index:
                continue

            params = self._parametros_index[tema_str]

            for field_name, field_desc, severity in fields:
                if field_name not in params or not params[field_name]:
                    gap = Gap(
                        tema=Tema(tema_str),
                        campo=field_name,
                        descricao=f"{field_desc} nao encontrado(a)",
                        severidade=severity,
                    )
                    gaps.append(gap)

        return gaps

    def get_parametros_by_tema(self, tema: Tema) -> Dict[str, Any]:
        """
        Retorna todos os parametros consolidados de um tema.

        Aplica hierarquia de prioridade para resolver conflitos.

        Args:
            tema: Tema a buscar

        Returns:
            Dicionario com parametros consolidados
        """
        if tema.value not in self._parametros_index:
            return {}

        resultado: Dict[str, Any] = {}
        params = self._parametros_index[tema.value]

        for param_key, values in params.items():
            if not values:
                continue

            # Ordena por prioridade do tipo de evento
            sorted_values = sorted(
                values,
                key=lambda x: self._get_priority(x[2])
            )

            # Usa o valor de maior prioridade
            resultado[param_key] = sorted_values[0][0]

        return resultado

    def get_fontes_by_tema(self, tema: Tema) -> List[str]:
        """
        Retorna todas as localizacoes/fontes de um tema.

        Args:
            tema: Tema a buscar

        Returns:
            Lista de localizacoes
        """
        extractions = self.get_by_tema(tema)
        fontes: List[str] = []
        for ext in extractions:
            if ext.localizacao and ext.localizacao not in fontes:
                fontes.append(ext.localizacao)
        return fontes

    def get_fatos_by_tema(self, tema: Tema) -> List[str]:
        """
        Retorna todos os fatos literais de um tema.

        Args:
            tema: Tema a buscar

        Returns:
            Lista de fatos literais
        """
        extractions = self.get_by_tema(tema)
        fatos: List[str] = []
        for ext in extractions:
            fatos.extend(ext.fatos_literais)
        return fatos

    def get_summary(self) -> Dict[str, Any]:
        """
        Retorna um resumo da memoria de processo.

        Returns:
            Dicionario com estatisticas da memoria
        """
        return {
            "total_extractions": len(self.extractions),
            "temas_encontrados": list(self.get_all_temas()),
            "eventos_encontrados": list(self.get_all_eventos()),
            "extracoes_por_tema": {
                tema: len(exts) for tema, exts in self.by_tema.items()
            },
            "extracoes_por_evento": {
                evento: len(exts) for evento, exts in self.by_evento.items()
            },
        }

    def clear(self) -> None:
        """Limpa toda a memoria."""
        self.extractions.clear()
        self.by_tema.clear()
        self.by_evento.clear()
        self._parametros_index.clear()

    @staticmethod
    def _normalize_value(value: Any) -> str:
        """
        Normaliza um valor para comparacao.

        Args:
            value: Valor a normalizar

        Returns:
            String normalizada
        """
        if value is None:
            return "none"

        if isinstance(value, str):
            return value.strip().lower()

        if isinstance(value, (int, float)):
            return str(value)

        return str(value).strip().lower()

    @staticmethod
    def _get_priority(tipo_evento: TipoEvento) -> int:
        """
        Retorna a prioridade de um tipo de evento.

        Hierarquia: sentenca > acordao > laudo > outros

        Args:
            tipo_evento: Tipo de evento

        Returns:
            Numero de prioridade (menor = maior prioridade)
        """
        priority_map: Dict[TipoEvento, int] = {
            TipoEvento.SENTENCA: 1,
            TipoEvento.ACORDAO: 2,
            TipoEvento.LAUDO: 3,
            TipoEvento.CALCULO: 4,
            TipoEvento.CTPS: 5,
            TipoEvento.HOLERITE: 6,
            TipoEvento.CONTRATO: 7,
            TipoEvento.PETICAO_INICIAL: 8,
            TipoEvento.CONTESTACAO: 9,
            TipoEvento.RECURSO: 10,
            TipoEvento.ATA_AUDIENCIA: 11,
            TipoEvento.DESPACHO: 12,
            TipoEvento.PROCURACAO: 13,
            TipoEvento.DOCUMENTO_PESSOAL: 14,
            TipoEvento.OUTROS: 99,
        }
        return priority_map.get(tipo_evento, 99)
