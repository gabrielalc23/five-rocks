"""
Validador de qualidade de resumos jurídicos.

Valida se o resumo gerado pela IA atende critérios mínimos de qualidade
e contém informações jurídicas relevantes.
"""
import json
import re
from typing import Dict, List, Optional, Tuple


class ResumeValidator:
    """
    Valida qualidade e completude de resumos jurídicos.
    
    Verifica:
    - Se o resumo está em formato JSON válido
    - Se contém campos obrigatórios
    - Se não contém informações claramente inventadas
    - Se tem tamanho mínimo adequado
    """
    
    REQUIRED_FIELDS = ['resumo_executivo']
    MIN_SUMMARY_LENGTH = 100  # caracteres mínimos no resumo executivo
    
    # Palavras que indicam informação inventada ou vaga
    VAGUE_INDICATORS = [
        'provavelmente',
        'possivelmente',
        'talvez',
        'pode ser',
        'não está claro',
        'não foi possível determinar',
    ]
    
    # Padrões que indicam alucinação (informação muito genérica)
    HALLUCINATION_PATTERNS = [
        r'^O documento trata.*$',  # Muito genérico
        r'^Este é um documento.*$',
        r'^O processo.*$',  # Sem detalhes
    ]
    
    def validate(self, summary: str) -> Tuple[bool, Optional[str], Dict]:
        """
        Valida um resumo jurídico.
        
        Args:
            summary: Resumo gerado pela IA (deve ser JSON)
            
        Returns:
            Tuple de (é_válido, mensagem_erro, dados_validados)
        """
        if not summary or not summary.strip():
            return False, "Resumo vazio", {}
        
        # Tenta parsear como JSON
        try:
            # Remove markdown code blocks se houver
            cleaned = summary.strip()
            if cleaned.startswith('```'):
                # Remove ```json ou ``` do início e fim
                cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
                cleaned = re.sub(r'\s*```$', '', cleaned)
            
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            return False, f"Resumo não está em formato JSON válido: {e}", {}
        
        # Valida campos obrigatórios
        missing_fields = [field for field in self.REQUIRED_FIELDS if field not in data]
        if missing_fields:
            return False, f"Campos obrigatórios ausentes: {', '.join(missing_fields)}", {}
        
        # Valida tamanho mínimo do resumo executivo
        resumo_executivo = data.get('resumo_executivo', '')
        if len(resumo_executivo) < self.MIN_SUMMARY_LENGTH:
            return False, f"Resumo executivo muito curto (mínimo {self.MIN_SUMMARY_LENGTH} caracteres)", {}
        
        # Verifica indicadores de informação vaga ou inventada
        warnings = []
        resumo_lower = resumo_executivo.lower()
        for indicator in self.VAGUE_INDICATORS:
            if indicator in resumo_lower:
                warnings.append(f"Possível informação vaga detectada: '{indicator}'")
        
        # Verifica padrões de alucinação
        for pattern in self.HALLUCINATION_PATTERNS:
            if re.match(pattern, resumo_executivo, re.IGNORECASE):
                warnings.append("Resumo muito genérico, pode não conter informações específicas")
        
        # Valida estrutura básica
        if not isinstance(data, dict):
            return False, "Resumo deve ser um objeto JSON", {}
        
        # Se passou todas as validações
        is_valid = len(warnings) == 0 or len(warnings) <= 1  # Permite 1 warning
        
        return is_valid, None if is_valid else f"Avisos: {'; '.join(warnings)}", data
    
    def extract_structured_data(self, summary: str) -> Optional[Dict]:
        """
        Extrai dados estruturados do resumo JSON.
        
        Args:
            summary: Resumo em formato JSON
            
        Returns:
            Dicionário com dados estruturados ou None se inválido
        """
        is_valid, error, data = self.validate(summary)
        if is_valid:
            return data
        return None
    
    def get_validation_report(self, summary: str) -> Dict:
        """
        Gera relatório completo de validação.
        
        Args:
            summary: Resumo a validar
            
        Returns:
            Dicionário com relatório de validação
        """
        is_valid, error, data = self.validate(summary)
        
        report = {
            'is_valid': is_valid,
            'error': error,
            'has_structured_data': data is not None and len(data) > 0,
            'field_count': len(data) if data else 0,
            'summary_length': len(summary),
        }
        
        if data:
            report['has_resumo_executivo'] = 'resumo_executivo' in data
            report['has_partes'] = 'partes' in data
            report['has_decisao'] = 'decisao' in data
            report['has_fundamentacao'] = 'fundamentacao' in data
        
        return report
