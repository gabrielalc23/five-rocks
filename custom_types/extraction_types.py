"""
Tipos de dados para o pipeline anti-alucinacao.

Define as estruturas de dados usadas nas camadas de extracao,
consolidacao e geracao de secoes.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional


class TipoEvento(str, Enum):
    """Tipos de eventos/documentos juridicos identificaveis."""
    SENTENCA = "sentenca"
    ACORDAO = "acordao"
    LAUDO = "laudo"
    CTPS = "ctps"
    HOLERITE = "holerite"
    PETICAO_INICIAL = "peticao_inicial"
    CONTESTACAO = "contestacao"
    RECURSO = "recurso"
    DESPACHO = "despacho"
    CALCULO = "calculo"
    CONTRATO = "contrato"
    DOCUMENTO_PESSOAL = "documento_pessoal"
    ATA_AUDIENCIA = "ata_audiencia"
    PROCURACAO = "procuracao"
    OUTROS = "outros"


class Tema(str, Enum):
    """Temas juridicos extraiveis de documentos trabalhistas."""
    JORNADA = "jornada"
    HORAS_EXTRAS = "horas_extras"
    ADICIONAL_NOTURNO = "adicional_noturno"
    FGTS = "fgts"
    MULTA_FGTS = "multa_fgts"
    FERIAS = "ferias"
    DECIMO_TERCEIRO = "decimo_terceiro"
    AVISO_PREVIO = "aviso_previo"
    VERBAS_RESCISORIAS = "verbas_rescisorias"
    DANOS_MORAIS = "danos_morais"
    DANOS_MATERIAIS = "danos_materiais"
    SALARIO = "salario"
    REMUNERACAO = "remuneracao"
    VINCULO_EMPREGATICIO = "vinculo_empregaticio"
    INTERVALO_INTRAJORNADA = "intervalo_intrajornada"
    INTERVALO_INTERJORNADA = "intervalo_interjornada"
    DSR = "dsr"  # Descanso Semanal Remunerado
    ADICIONAL_INSALUBRIDADE = "adicional_insalubridade"
    ADICIONAL_PERICULOSIDADE = "adicional_periculosidade"
    EQUIPARACAO_SALARIAL = "equiparacao_salarial"
    DESVIO_FUNCAO = "desvio_funcao"
    ACUMULO_FUNCAO = "acumulo_funcao"
    ESTABILIDADE = "estabilidade"
    REINTEGRACAO = "reintegracao"
    VALE_TRANSPORTE = "vale_transporte"
    VALE_ALIMENTACAO = "vale_alimentacao"
    PLR = "plr"  # Participacao nos Lucros e Resultados
    HONORARIOS = "honorarios"
    CUSTAS = "custas"
    JUROS = "juros"
    CORRECAO_MONETARIA = "correcao_monetaria"
    COMPENSACAO = "compensacao"
    PRESCRICAO = "prescricao"
    OUTROS = "outros"


class StatusConsolidacao(str, Enum):
    """Status da consolidacao de um tema."""
    CONFIRMED = "confirmed"      # Informacao confirmada sem conflitos
    DIVERGENT = "divergent"      # Existem conflitos entre fontes
    PENDING = "pending"          # Informacao incompleta ou ausente


class ValidationSeverity(str, Enum):
    """Severidade das regras de validacao."""
    ERROR = "error"      # Bloqueia e requer re-geracao
    WARNING = "warning"  # Apenas log, nao bloqueia


@dataclass
class Conflict:
    """Representa um conflito entre extracoes."""
    tema: Tema
    campo: str
    valor_1: Any
    fonte_1: str
    valor_2: Any
    fonte_2: str
    resolucao: Optional[str] = None
    fonte_escolhida: Optional[str] = None


@dataclass
class Gap:
    """Representa uma lacuna de informacao."""
    tema: Tema
    campo: str
    descricao: str
    severidade: ValidationSeverity = ValidationSeverity.WARNING


@dataclass
class ChunkExtraction:
    """
    Resultado da extracao factual de um chunk (Layer 2 output).

    Cada extracao representa os fatos extraidos literalmente de um
    trecho do documento, sem interpretacao.
    """
    chunk_id: str
    tipo_evento: TipoEvento
    temas: List[Tema]
    fatos_literais: List[str]  # Texto EXATO do documento
    parametros: Dict[str, Any]  # datas, percentuais, valores
    localizacao: str  # fls. XX / evento XX / pagina XX
    texto_original: str  # chunk para verificacao
    confianca: float = 1.0  # 0-1, confianca na extracao

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionario."""
        return {
            "chunk_id": self.chunk_id,
            "tipo_evento": self.tipo_evento.value,
            "temas": [t.value for t in self.temas],
            "fatos_literais": self.fatos_literais,
            "parametros": self.parametros,
            "localizacao": self.localizacao,
            "texto_original": self.texto_original[:200] + "..." if len(self.texto_original) > 200 else self.texto_original,
            "confianca": self.confianca,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], texto_original: str = "") -> "ChunkExtraction":
        """Cria instancia a partir de dicionario."""
        return cls(
            chunk_id=data.get("chunk_id", ""),
            tipo_evento=TipoEvento(data.get("tipo_evento", "outros")),
            temas=[Tema(t) for t in data.get("temas", [])],
            fatos_literais=data.get("fatos_literais", []),
            parametros=data.get("parametros", {}),
            localizacao=data.get("localizacao", "nao informado"),
            texto_original=texto_original or data.get("texto_original", ""),
            confianca=data.get("confianca", 1.0),
        )


@dataclass
class ConsolidatedTheme:
    """
    Resultado da consolidacao semantica de um tema (Layer 4 output).

    Representa a visao consolidada de um tema apos resolver conflitos
    e identificar pendencias entre multiplas extracoes.
    """
    tema: Tema
    status: StatusConsolidacao
    parametros_consolidados: Dict[str, Any]
    fontes: List[str]  # localizacoes de origem
    conflitos: List[Conflict] = field(default_factory=list)
    observacoes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionario."""
        return {
            "tema": self.tema.value,
            "status": self.status.value,
            "parametros_consolidados": self.parametros_consolidados,
            "fontes": self.fontes,
            "conflitos": [
                {
                    "campo": c.campo,
                    "valor_1": c.valor_1,
                    "fonte_1": c.fonte_1,
                    "valor_2": c.valor_2,
                    "fonte_2": c.fonte_2,
                    "resolucao": c.resolucao,
                }
                for c in self.conflitos
            ],
            "observacoes": self.observacoes,
        }


@dataclass
class ValidationError:
    """Erro de validacao de uma secao."""
    secao: str
    regra: str
    mensagem: str
    severidade: ValidationSeverity
    campo: Optional[str] = None
    valor: Optional[Any] = None


@dataclass
class SectionResult:
    """
    Resultado da geracao de uma secao (Layer 5 output).

    Representa uma das 9 secoes do resumo final, com seu conteudo
    e metadados de validacao.
    """
    secao: str  # nome da secao
    conteudo: Dict[str, Any]  # conteudo gerado
    fontes_utilizadas: List[str]  # localizacoes referenciadas
    validacao_ok: bool = True
    erros_validacao: List[ValidationError] = field(default_factory=list)
    tentativas: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionario."""
        return {
            "secao": self.secao,
            "conteudo": self.conteudo,
            "fontes_utilizadas": self.fontes_utilizadas,
            "validacao_ok": self.validacao_ok,
            "erros_validacao": [
                {
                    "regra": e.regra,
                    "mensagem": e.mensagem,
                    "severidade": e.severidade.value,
                }
                for e in self.erros_validacao
            ],
            "tentativas": self.tentativas,
        }


@dataclass
class PipelineResult:
    """Resultado final do pipeline anti-alucinacao."""
    secoes: List[SectionResult]
    total_chunks: int
    total_extracoes: int
    temas_consolidados: int
    conflitos_encontrados: int
    pendencias: List[str]
    tempo_processamento_ms: float = 0.0

    def to_json(self) -> Dict[str, Any]:
        """Converte resultado final para JSON estruturado."""
        resultado: Dict[str, Any] = {}

        for secao in self.secoes:
            resultado[secao.secao] = secao.conteudo

        resultado["_metadata"] = {
            "total_chunks": self.total_chunks,
            "total_extracoes": self.total_extracoes,
            "temas_consolidados": self.temas_consolidados,
            "conflitos_encontrados": self.conflitos_encontrados,
            "pendencias": self.pendencias,
            "tempo_processamento_ms": self.tempo_processamento_ms,
        }

        return resultado
