from typing import Optional, Dict
from utils.legal_metadata_extractor import LegalMetadata


class LegalPromptBuilder:

    BASE_SYSTEM_PROMPT: str = """Você é um assistente jurídico especializado em análise e resumo de documentos processuais brasileiros.

REGRAS CRÍTICAS:
1. NUNCA invente informações que não estão explicitamente no texto fornecido
2. Se uma informação não estiver clara ou ausente, use "não informado" ou "não identificado"
3. Baseie-se APENAS no texto fornecido - não use conhecimento externo
4. Mantenha terminologia jurídica precisa e correta
5. Preserve números, datas e valores exatamente como aparecem no texto
6. Diferencie claramente: FATOS, FUNDAMENTAÇÃO e DECISÃO/DISPOSITIVO

FORMATO DE RESPOSTA:
Você DEVE responder em JSON válido com a seguinte estrutura:
{
  "resumo_executivo": "Resumo geral em 2-3 parágrafos",
  "numero_processo": "número do processo se identificado",
  "tribunal": "tribunal se identificado",
  "partes": {
    "autor": "nome se identificado",
    "reu": "nome se identificado",
    "outras_partes": ["lista de outras partes"]
  },
  "tipo_acao": "tipo de ação se identificado",
  "tipo_documento": "petição inicial / sentença / acórdão / despacho / etc",
  "fatos_relevantes": ["lista de fatos principais"],
  "fundamentacao": "fundamentação jurídica resumida",
  "decisao": "decisão ou dispositivo se houver",
  "pedidos": ["lista de pedidos se houver"],
  "observacoes": "observações relevantes"
}

IMPORTANTE: Responda APENAS com o JSON, sem texto adicional antes ou depois."""

    PROMPTS_BY_DOCUMENT_TYPE: Dict[str, str] = {
        "petição inicial": """DOCUMENTO: PETIÇÃO INICIAL

Extraia e resuma:
1. Partes (autor e réu)
2. Tipo de ação
3. Fatos narrados
4. Fundamentação jurídica
5. Pedidos (específicos e genéricos)
6. Documentos anexos mencionados

Foque nos pedidos e na fundamentação, pois são críticos para entender o caso.""",
        "sentença": """DOCUMENTO: SENTENÇA

Extraia e resuma:
1. Relatório (resumo dos fatos e procedimento)
2. Fundamentação (razões de decidir)
3. DISPOSITIVO (decisão final - procedente/improcedente/parcial)
4. Valor da condenação se houver
5. Custas e honorários

O DISPOSITIVO é a parte mais importante - destaque claramente.""",
        "acórdão": """DOCUMENTO: ACÓRDÃO

Extraia e resuma:
1. Relatório (histórico do caso)
2. Votos dos desembargadores/ministros
3. Fundamentação da decisão
4. DISPOSITIVO (decisão final)
5. Se houve reforma da decisão anterior
6. Se houve provimento ou improvimento do recurso

Destaque se houve divergência entre os votos.""",
        "despacho": """DOCUMENTO: DESPACHO/DECISÃO INTERLOCUTÓRIA

Extraia e resuma:
1. Matéria decidida
2. Fundamentação breve
3. Decisão (deferido/indeferido/indeferido em parte)
4. Prazo determinado se houver
5. Intimação de partes se houver

Despachos são decisões intermediárias - foque na decisão específica.""",
        "contestação": """DOCUMENTO: CONTESTAÇÃO

Extraia e resuma:
1. Defesas apresentadas (preliminares e de mérito)
2. Fatos admitidos e negados
3. Fundamentação da defesa
4. Pedido de julgamento (improcedência, etc)
5. Reconvenção se houver

Foque nas defesas e na fundamentação contrária aos pedidos do autor.""",
    }

    def build_prompt(
        self,
        document_type: Optional[str] = None,
        metadata: Optional[LegalMetadata] = None,
    ) -> str:
        prompt: str = self.BASE_SYSTEM_PROMPT

        # Adiciona instruções específicas do tipo de documento
        if document_type and document_type in self.PROMPTS_BY_DOCUMENT_TYPE:
            prompt += "\n\n" + self.PROMPTS_BY_DOCUMENT_TYPE[document_type]

        # Adiciona validação de metadados se disponível
        if metadata:
            validation = "\n\nVALIDAÇÃO:"
            if metadata.process_number:
                validation += (
                    f"\n- Número do processo deve ser: {metadata.process_number}"
                )
            if metadata.tribunal:
                validation += f"\n- Tribunal deve ser: {metadata.tribunal}"
            if metadata.partes:
                validation += f"\n- Partes esperadas: {', '.join(metadata.partes[:3])}"
            validation += "\nSe encontrar informações diferentes no texto, use as do texto (pode haver erro na extração automática)."
            prompt += validation

        return prompt

    def get_default_prompt(self) -> str:
        return self.BASE_SYSTEM_PROMPT
