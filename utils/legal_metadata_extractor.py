"""
Extrator de metadados jurídicos de documentos processuais.

Extrai informações estruturadas como número do processo, tribunal, partes, etc.
antes do resumo para garantir que essas informações estejam sempre presentes.
"""
import re
from typing import Dict, Optional, List
from dataclasses import dataclass, field


@dataclass
class LegalMetadata:
    """Metadados jurídicos extraídos de um documento."""
    process_number: Optional[str] = None
    tribunal: Optional[str] = None
    comarca: Optional[str] = None
    partes: List[str] = field(default_factory=list)
    tipo_acao: Optional[str] = None
    tipo_documento: Optional[str] = None
    data_documento: Optional[str] = None
    
    def __init__(self, **kwargs):
        """Inicialização customizada para garantir partes como lista vazia."""
        self.process_number = kwargs.get('process_number')
        self.tribunal = kwargs.get('tribunal')
        self.comarca = kwargs.get('comarca')
        self.partes = kwargs.get('partes', [])
        self.tipo_acao = kwargs.get('tipo_acao')
        self.tipo_documento = kwargs.get('tipo_documento')
        self.data_documento = kwargs.get('data_documento')


class LegalMetadataExtractor:
    """
    Extrai metadados jurídicos de textos de processos judiciais.
    
    Usa regex e padrões conhecidos do sistema judiciário brasileiro
    para identificar informações críticas.
    """
    
    # Padrão CNJ: NNNNNNN-DD.AAAA.J.TR.OOOO
    PROCESS_NUMBER_PATTERN = re.compile(
        r'\b\d{7}[-.]?\d{2}[./]?\d{4}[./]?\d{1}[./]?\d{2}[./]?\d{4}\b'
    )
    
    # Tribunais comuns
    TRIBUNAL_PATTERNS = {
        'TJSP': r'Tribunal de Justiça de São Paulo|TJSP|TJ/SP',
        'TJRJ': r'Tribunal de Justiça do Rio de Janeiro|TJRJ|TJ/RJ',
        'TJMG': r'Tribunal de Justiça de Minas Gerais|TJMG|TJ/MG',
        'TRF1': r'Tribunal Regional Federal da 1ª Região|TRF1|TRF-1',
        'TRF2': r'Tribunal Regional Federal da 2ª Região|TRF2|TRF-2',
        'TRF3': r'Tribunal Regional Federal da 3ª Região|TRF3|TRF-3',
        'TRF4': r'Tribunal Regional Federal da 4ª Região|TRF4|TRF-4',
        'TRF5': r'Tribunal Regional Federal da 5ª Região|TRF5|TRF-5',
        'TRT1': r'Tribunal Regional do Trabalho da 1ª Região|TRT1|TRT-1',
        'STJ': r'Superior Tribunal de Justiça|STJ',
        'STF': r'Supremo Tribunal Federal|STF',
        'TST': r'Tribunal Superior do Trabalho|TST',
    }
    
    # Tipos de documentos jurídicos
    DOCUMENT_TYPES = {
        'petição inicial': r'petição\s+inicial|inicial',
        'sentença': r'sentença|julgamento\s+procedente|julgamento\s+improcedente',
        'acórdão': r'acórdão|decisão\s+do\s+tribunal',
        'despacho': r'despacho|decisão\s+interlocutória',
        'contestação': r'contestação',
        'recurso': r'recurso|apelação|agravo',
        'intimação': r'intimação',
    }
    
    # Tipos de ações comuns
    ACTION_TYPES = {
        'ação de cobrança': r'ação\s+de\s+cobrança|cobrança',
        'ação indenizatória': r'ação\s+indenizatória|indenização',
        'ação trabalhista': r'ação\s+trabalhista|reclamação\s+trabalhista',
        'ação de despejo': r'ação\s+de\s+despejo|despejo',
        'ação de execução': r'ação\s+de\s+execução|execução',
        'mandado de segurança': r'mandado\s+de\s+segurança',
        'ação de alimentos': r'ação\s+de\s+alimentos|alimentos',
    }
    
    # Padrões para identificar partes
    PARTE_PATTERNS = [
        r'autor[ae]?[:\s]+([A-Z][A-Za-z\s]+)',
        r'ré[ur][:\s]+([A-Z][A-Za-z\s]+)',
        r'requerente[:\s]+([A-Z][A-Za-z\s]+)',
        r'requerido[:\s]+([A-Z][A-Za-z\s]+)',
        r'recorrente[:\s]+([A-Z][A-Za-z\s]+)',
        r'recorrido[:\s]+([A-Z][A-Za-z\s]+)',
    ]
    
    # Padrões de data
    DATE_PATTERNS = [
        r'\d{1,2}[/-]\d{1,2}[/-]\d{4}',
        r'\d{4}[/-]\d{1,2}[/-]\d{1,2}',
        r'\d{1,2}\s+de\s+\w+\s+de\s+\d{4}',
    ]
    
    def extract(self, text: str) -> LegalMetadata:
        """
        Extrai metadados jurídicos do texto.
        
        Args:
            text: Texto do documento jurídico
            
        Returns:
            LegalMetadata com informações extraídas
        """
        metadata = LegalMetadata()
        
        # Extrai número do processo
        metadata.process_number = self._extract_process_number(text)
        
        # Extrai tribunal
        metadata.tribunal = self._extract_tribunal(text)
        
        # Extrai comarca (geralmente após tribunal)
        metadata.comarca = self._extract_comarca(text)
        
        # Extrai partes
        metadata.partes = self._extract_partes(text)
        
        # Extrai tipo de ação
        metadata.tipo_acao = self._extract_action_type(text)
        
        # Extrai tipo de documento
        metadata.tipo_documento = self._extract_document_type(text)
        
        # Extrai data do documento
        metadata.data_documento = self._extract_date(text)
        
        return metadata
    
    def _extract_process_number(self, text: str) -> Optional[str]:
        """Extrai número do processo no padrão CNJ."""
        matches = self.PROCESS_NUMBER_PATTERN.findall(text)
        if matches:
            # Normaliza formato
            process = matches[0].replace('.', '').replace('/', '').replace('-', '')
            if len(process) == 20:
                # Formata: NNNNNNN-DD.AAAA.J.TR.OOOO
                return f"{process[:7]}-{process[7:9]}.{process[9:13]}.{process[13:14]}.{process[14:16]}.{process[16:]}"
            return matches[0]
        return None
    
    def _extract_tribunal(self, text: str) -> Optional[str]:
        """Extrai tribunal mencionado no texto."""
        text_upper = text.upper()
        for tribunal, pattern in self.TRIBUNAL_PATTERNS.items():
            if re.search(pattern, text_upper, re.IGNORECASE):
                return tribunal
        return None
    
    def _extract_comarca(self, text: str) -> Optional[str]:
        """Extrai comarca (geralmente após 'Comarca de' ou similar)."""
        patterns = [
            r'comarca\s+de\s+([A-Z][A-Za-z\s]+)',
            r'foro\s+de\s+([A-Z][A-Za-z\s]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None
    
    def _extract_partes(self, text: str) -> List[str]:
        """Extrai partes envolvidas no processo."""
        partes = []
        for pattern in self.PARTE_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                parte = match.group(1).strip()
                # Limita tamanho (nomes muito longos provavelmente são erros)
                if len(parte) < 100 and parte not in partes:
                    partes.append(parte)
        return partes[:10]  # Limita a 10 partes
    
    def _extract_action_type(self, text: str) -> Optional[str]:
        """Extrai tipo de ação."""
        text_lower = text.lower()
        for action_type, pattern in self.ACTION_TYPES.items():
            if re.search(pattern, text_lower):
                return action_type
        return None
    
    def _extract_document_type(self, text: str) -> Optional[str]:
        """Extrai tipo de documento jurídico."""
        text_lower = text.lower()
        for doc_type, pattern in self.DOCUMENT_TYPES.items():
            if re.search(pattern, text_lower):
                return doc_type
        return None
    
    def _extract_date(self, text: str) -> Optional[str]:
        """Extrai data do documento (primeira data encontrada)."""
        for pattern in self.DATE_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        return None
