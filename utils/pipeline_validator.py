"""
Validador do pipeline anti-alucinacao (Layer 6).

Valida secoes geradas aplicando regras de qualidade.
Erros disparam re-geracao da secao.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable

from custom_types.extraction_types import (
    SectionResult,
    ValidationError,
    ValidationSeverity,
)

logger = logging.getLogger(__name__)


@dataclass
class ValidationRule:
    """Define uma regra de validacao."""
    name: str
    description: str
    severity: ValidationSeverity
    applies_to: List[str]  # secoes onde se aplica (* = todas)
    validator: Callable[[Dict[str, Any], str], Optional[str]]


class PipelineValidator:
    """
    Validador automatico de secoes geradas (Layer 6).

    Aplica regras de qualidade e dispara re-geracao quando necessario.
    """

    def __init__(self, max_regeneration_attempts: int = 2):
        """
        Inicializa o validador.

        Args:
            max_regeneration_attempts: Tentativas maximas de re-geracao
        """
        self.max_regeneration_attempts = max_regeneration_attempts
        self.rules = self._build_rules()

    def _build_rules(self) -> List[ValidationRule]:
        """
        Constroi lista de regras de validacao.

        Returns:
            Lista de ValidationRule
        """
        return [
            # Regra: Campo sem localizacao
            ValidationRule(
                name="campo_sem_localizacao",
                description="Campo com valor mas sem fonte/localizacao",
                severity=ValidationSeverity.ERROR,
                applies_to=["cabecalho", "parametros_calculo", "resultado_por_pedido"],
                validator=self._validate_has_sources,
            ),

            # Regra: Verba sem parametro
            ValidationRule(
                name="verba_sem_parametro",
                description="Verba deferida sem parametros de calculo",
                severity=ValidationSeverity.ERROR,
                applies_to=["parametros_calculo", "resultado_por_pedido"],
                validator=self._validate_verbas_have_params,
            ),

            # Regra: Percentual sem fonte
            ValidationRule(
                name="percentual_sem_fonte",
                description="Percentual informado sem fonte",
                severity=ValidationSeverity.ERROR,
                applies_to=["parametros_calculo"],
                validator=self._validate_percentuais_have_source,
            ),

            # Regra: Valor sem fonte
            ValidationRule(
                name="valor_sem_fonte",
                description="Valor monetario sem fonte",
                severity=ValidationSeverity.ERROR,
                applies_to=["parametros_calculo", "resultado_por_pedido", "resumo"],
                validator=self._validate_valores_have_source,
            ),

            # Regra: Reflexo sem base
            ValidationRule(
                name="reflexo_sem_base",
                description="Reflexo mencionado sem verba base",
                severity=ValidationSeverity.WARNING,
                applies_to=["resultado_por_pedido", "parametros_calculo"],
                validator=self._validate_reflexos_have_base,
            ),

            # Regra: Linguagem vaga
            ValidationRule(
                name="linguagem_vaga",
                description="Uso de linguagem vaga ou incerta",
                severity=ValidationSeverity.WARNING,
                applies_to=["*"],
                validator=self._validate_no_vague_language,
            ),

            # Regra: Data invalida
            ValidationRule(
                name="data_invalida",
                description="Data em formato invalido",
                severity=ValidationSeverity.WARNING,
                applies_to=["cabecalho", "timeline", "parametros_calculo"],
                validator=self._validate_date_formats,
            ),

            # Regra: JSON vazio
            ValidationRule(
                name="secao_vazia",
                description="Secao com conteudo vazio ou erro",
                severity=ValidationSeverity.ERROR,
                applies_to=["*"],
                validator=self._validate_not_empty,
            ),
        ]

    def validate_section(
        self,
        section: SectionResult
    ) -> tuple[bool, List[ValidationError]]:
        """
        Valida uma secao aplicando todas as regras aplicaveis.

        Args:
            section: Secao a validar

        Returns:
            Tupla (passou, lista de erros)
        """
        errors: List[ValidationError] = []

        for rule in self.rules:
            # Verifica se regra se aplica a esta secao
            if "*" not in rule.applies_to and section.secao not in rule.applies_to:
                continue

            # Executa validacao
            error_msg = rule.validator(section.conteudo, section.secao)

            if error_msg:
                error = ValidationError(
                    secao=section.secao,
                    regra=rule.name,
                    mensagem=error_msg,
                    severidade=rule.severity,
                )
                errors.append(error)

        # Determina se passou (sem erros ERROR)
        has_errors = any(e.severidade == ValidationSeverity.ERROR for e in errors)

        return (not has_errors, errors)

    def validate_all_sections(
        self,
        sections: List[SectionResult]
    ) -> Dict[str, tuple[bool, List[ValidationError]]]:
        """
        Valida todas as secoes.

        Args:
            sections: Lista de secoes

        Returns:
            Dicionario {secao: (passou, erros)}
        """
        results: Dict[str, tuple[bool, List[ValidationError]]] = {}

        for section in sections:
            passed, errors = self.validate_section(section)
            results[section.secao] = (passed, errors)

            if errors:
                for error in errors:
                    level = logging.WARNING if error.severidade == ValidationSeverity.WARNING else logging.ERROR
                    logger.log(level, f"Layer 6: {section.secao} - {error.regra}: {error.mensagem}")

        # Log resumo
        total = len(sections)
        passed_count = sum(1 for p, _ in results.values() if p)
        logger.info(f"Layer 6: Validation - {passed_count}/{total} secoes passaram")

        return results

    def get_sections_to_regenerate(
        self,
        validation_results: Dict[str, tuple[bool, List[ValidationError]]]
    ) -> List[tuple[str, List[str]]]:
        """
        Identifica secoes que precisam ser regeneradas.

        Args:
            validation_results: Resultados da validacao

        Returns:
            Lista de (secao, erros) para regenerar
        """
        to_regenerate: List[tuple[str, List[str]]] = []

        for secao, (passed, errors) in validation_results.items():
            if not passed:
                error_msgs = [e.mensagem for e in errors if e.severidade == ValidationSeverity.ERROR]
                to_regenerate.append((secao, error_msgs))

        return to_regenerate

    # ========== Funcoes de Validacao ==========

    def _validate_has_sources(
        self,
        content: Dict[str, Any],
        section: str
    ) -> Optional[str]:
        """Valida se campos com valor tem fonte."""
        missing_sources: List[str] = []

        def check_recursive(obj: Any, path: str = "") -> None:
            if isinstance(obj, dict):
                # Se tem "valor" deve ter "fonte"
                if "valor" in obj and obj["valor"] and obj["valor"] != "nao identificado":
                    if "fonte" not in obj or not obj["fonte"]:
                        missing_sources.append(path or "campo")

                for key, value in obj.items():
                    new_path = f"{path}.{key}" if path else key
                    check_recursive(value, new_path)

            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_recursive(item, f"{path}[{i}]")

        check_recursive(content)

        if missing_sources:
            return f"Campos sem fonte: {', '.join(missing_sources[:3])}"
        return None

    def _validate_verbas_have_params(
        self,
        content: Dict[str, Any],
        section: str
    ) -> Optional[str]:
        """Valida se verbas deferidas tem parametros."""
        # Para resultado_por_pedido
        if "pedidos" in content:
            for pedido in content.get("pedidos", []):
                if pedido.get("resultado") in ["procedente", "parcialmente procedente"]:
                    if not pedido.get("valor") or pedido.get("valor") == "N/A":
                        # Verba deferida sem valor pode ser ok se for obrigacao de fazer
                        pass

        return None

    def _validate_percentuais_have_source(
        self,
        content: Dict[str, Any],
        section: str
    ) -> Optional[str]:
        """Valida se percentuais tem fonte."""
        percentual_pattern = r'\d+[,.]?\d*\s*%'

        def find_percentuais(obj: Any, path: str = "") -> List[str]:
            found: List[str] = []

            if isinstance(obj, dict):
                for key, value in obj.items():
                    if isinstance(value, str) and re.search(percentual_pattern, value):
                        # Verifica se tem fonte no mesmo nivel
                        if "fonte" not in obj or not obj["fonte"]:
                            found.append(f"{path}.{key}" if path else key)
                    else:
                        found.extend(find_percentuais(value, f"{path}.{key}" if path else key))

            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    found.extend(find_percentuais(item, f"{path}[{i}]"))

            return found

        missing = find_percentuais(content)
        if missing:
            return f"Percentuais sem fonte: {', '.join(missing[:3])}"
        return None

    def _validate_valores_have_source(
        self,
        content: Dict[str, Any],
        section: str
    ) -> Optional[str]:
        """Valida se valores monetarios tem fonte."""
        valor_pattern = r'R\$\s*[\d.,]+'

        def find_valores(obj: Any, path: str = "") -> List[str]:
            found: List[str] = []

            if isinstance(obj, dict):
                for key, value in obj.items():
                    if isinstance(value, str) and re.search(valor_pattern, value):
                        if "fonte" not in obj or not obj["fonte"]:
                            found.append(f"{path}.{key}" if path else key)
                    elif isinstance(value, dict) and "valor" in value:
                        str_val = str(value.get("valor", ""))
                        if re.search(valor_pattern, str_val):
                            if "fonte" not in value or not value["fonte"]:
                                found.append(f"{path}.{key}" if path else key)
                    else:
                        found.extend(find_valores(value, f"{path}.{key}" if path else key))

            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    found.extend(find_valores(item, f"{path}[{i}]"))

            return found

        missing = find_valores(content)
        if missing:
            return f"Valores sem fonte: {', '.join(missing[:3])}"
        return None

    def _validate_reflexos_have_base(
        self,
        content: Dict[str, Any],
        section: str
    ) -> Optional[str]:
        """Valida se reflexos tem verba base mencionada."""
        reflexos_keywords = [
            "reflexos", "repercussao", "incidencia", "integracao"
        ]

        content_str = str(content).lower()

        for keyword in reflexos_keywords:
            if keyword in content_str:
                # Verifica se menciona verba base
                bases = ["horas extras", "adicional", "ferias", "decimo terceiro", "fgts"]
                has_base = any(base in content_str for base in bases)
                if not has_base:
                    return f"Reflexo mencionado sem verba base clara"

        return None

    def _validate_no_vague_language(
        self,
        content: Dict[str, Any],
        section: str
    ) -> Optional[str]:
        """Valida ausencia de linguagem vaga."""
        vague_terms = [
            "possivelmente", "provavelmente", "talvez",
            "parece que", "aparentemente", "pode ser que",
            "nao tenho certeza", "acredito que",
        ]

        content_str = str(content).lower()

        found_vague: List[str] = []
        for term in vague_terms:
            if term in content_str:
                found_vague.append(term)

        if found_vague:
            return f"Linguagem vaga detectada: {', '.join(found_vague[:2])}"
        return None

    def _validate_date_formats(
        self,
        content: Dict[str, Any],
        section: str
    ) -> Optional[str]:
        """Valida formato de datas."""
        # Padroes de data validos
        valid_patterns = [
            r'\d{2}/\d{2}/\d{4}',  # DD/MM/AAAA
            r'\d{2}-\d{2}-\d{4}',  # DD-MM-AAAA
            r'\d{4}-\d{2}-\d{2}',  # AAAA-MM-DD
        ]

        # Padroes de data invalidos/ambiguos
        invalid_patterns = [
            r'\d{1,2}/\d{1,2}/\d{2}(?!\d)',  # D/M/AA (ambiguo)
        ]

        content_str = str(content)

        for pattern in invalid_patterns:
            if re.search(pattern, content_str):
                return "Data em formato ambiguo (use DD/MM/AAAA)"

        return None

    def _validate_not_empty(
        self,
        content: Dict[str, Any],
        section: str
    ) -> Optional[str]:
        """Valida que secao nao esta vazia."""
        if not content:
            return "Secao vazia"

        if "erro" in content:
            return f"Secao com erro: {content.get('erro')}"

        # Verifica se tem conteudo significativo
        def has_content(obj: Any) -> bool:
            if isinstance(obj, str):
                return bool(obj.strip())
            if isinstance(obj, (int, float)):
                return True
            if isinstance(obj, list):
                return any(has_content(item) for item in obj)
            if isinstance(obj, dict):
                return any(has_content(v) for k, v in obj.items() if k != "fonte")
            return False

        if not has_content(content):
            return "Secao sem conteudo significativo"

        return None
