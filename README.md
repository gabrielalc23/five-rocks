# 📚 Five Rocks - Bot de Sumarização de Processos Judiciais

Sistema de IA especializado em resumir documentos jurídicos brasileiros (petições, sentenças, acórdãos, despachos) usando OpenAI GPT. Desenvolvido para advogados que precisam processar grandes volumes de documentos processuais de forma eficiente e precisa.

## 🎯 Características Principais

- ✅ **Resumos Jurídicos Especializados**: Prompts específicos para cada tipo de documento (petição inicial, sentença, acórdão, despacho)
- ✅ **Estrutura Padronizada**: Resumos em formato JSON estruturado com metadados jurídicos
- ✅ **Extração Automática de Metadados**: Identifica número do processo, tribunal, partes, tipo de ação
- ✅ **Validação de Qualidade**: Validação automática dos resumos gerados
- ✅ **Tratamento Robusto de Erros**: Detecta e trata PDFs protegidos, corrompidos, DOCX com problemas
- ✅ **Otimização de Custos**: Usa `gpt-4o-mini` e otimiza tokens para reduzir custos
- ✅ **Processamento Paralelo**: Processa múltiplos documentos simultaneamente com controle de concorrência
- ✅ **Suporte a Documentos Grandes**: Processa documentos de 2000+ páginas com estratégia hierárquica

## 📋 Índice

- [Instalação](#-instalação)
- [Configuração](#-configuração)
- [Uso Básico](#-uso-básico)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Arquitetura](#-arquitetura)
- [Formato de Resumo](#-formato-de-resumo)
- [Tratamento de Erros](#-tratamento-de-erros)
- [Otimizações](#-otimizações)
- [Troubleshooting](#-troubleshooting)
- [Documentação Técnica](#-documentação-técnica)

## 🚀 Instalação

### Pré-requisitos

- Python 3.10 ou superior
- pip (gerenciador de pacotes Python)
- Chave de API da OpenAI

### Passo a Passo

1. **Clone o repositório** (ou navegue até o diretório do projeto):
```bash
cd five-rocks
```

2. **Crie um ambiente virtual** (recomendado):
```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou
.venv\Scripts\activate  # Windows
```

3. **Instale as dependências**:
```bash
pip install -r requirements.txt
```

4. **Configure as variáveis de ambiente**:
```bash
cp .env.example .env  # Se houver arquivo de exemplo
# Ou crie um arquivo .env manualmente
```

5. **Adicione sua chave da OpenAI no arquivo `.env`**:
```env
OPENAI_API_KEY=sua_chave_aqui
```

## ⚙️ Configuração

### Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto com:

```env
OPENAI_API_KEY=sua_chave_da_openai_aqui
```

### Configuração do Modelo

Por padrão, o sistema usa `gpt-4o-mini` para otimizar custos. Você pode alterar o modelo no código:

```python
from core.openai_summarizer import OpenAISummarizer

summarizer = OpenAISummarizer(
    model="gpt-4o-mini",  # ou "gpt-4o", "gpt-3.5-turbo", etc.
    max_retries=3,
    max_parallel_chunks=5
)
```

### Diretório de Dados

Por padrão, o sistema procura documentos na pasta `data/`. Você pode alterar isso em `config.py`:

```python
DATA_DIR = "data"  # Altere para o caminho desejado
```

## 📖 Uso Básico

### Uso Simples

1. **Coloque seus documentos** na pasta `data/`:
   - Arquivos PDF (`.pdf`)
   - Arquivos Word (`.docx`)

2. **Execute o script principal**:
```bash
python3 main.py
```

3. **Aguarde o processamento**. O sistema irá:
   - Encontrar todos os arquivos PDF e DOCX
   - Processar cada um em paralelo (máximo 3 simultâneos)
   - Gerar resumos estruturados em JSON
   - Exibir resultados no console

### Exemplo de Saída

```
============================================================
 📚 BOT DE SUMARIZAÇÃO DE PROCESSOS (ASYNC)
============================================================

🔍 Encontrados: 8 arquivo(s) para processar (4 PDF(s), 4 DOCX(s))
Processando: 0012197-59.2022.5.15.0135_1grau.pdf
Processando: 0011037-65.2018.5.15.0126_1grau.pdf
...
  [1/8] ✓ 0012197-59.2022.5.15.0135 Leitura Processo.docx
  [2/8] ✓ 0010466-09.2022.5.15.0012 Leitura Processo.docx
...

============================================================
 RESULTADOS - TODOS OS ARQUIVOS
============================================================

📊 Processados: 8 | Sucesso: 8 | Erros: 0 | Taxa: 100.0% | Tempo: 125000ms

📄 Resumos gerados:
----------------------------------------

▶ 0012197-59.2022.5.15.0135 Leitura Processo.docx
  Palavras: 15234 | Tempo: 21792ms
  {
    "resumo_executivo": "...",
    "numero_processo": "0012197-59.2022.5.15.0135",
    ...
  }
```

### Uso Programático

```python
import asyncio
from adapters import PdfAdapter, DocxAdapter
from core.openai_summarizer import OpenAISummarizer
from services.document_service import DocumentService

async def process_document():
    # Inicializa componentes
    summarizer = OpenAISummarizer()
    adapter = PdfAdapter()  # ou DocxAdapter()
    
    # Cria serviço
    service = DocumentService(
        adapter=adapter,
        summarizer=summarizer
    )
    
    # Processa arquivo
    result = await service.process_file("data/processo.pdf")
    
    if result.is_success:
        print(f"Resumo: {result.summary}")
        print(f"Palavras: {result.word_count}")
    else:
        print(f"Erro: {result.error_message}")

# Executa
asyncio.run(process_document())
```

## 📁 Estrutura do Projeto

```
five-rocks/
├── adapters/              # Adaptadores para leitura de documentos
│   ├── base_adapter.py    # Interface base
│   ├── pdf_adapter.py    # Leitor de PDFs
│   └── docx_adapter.py   # Leitor de DOCX
│
├── core/                  # Núcleo do sistema
│   ├── base_summarizer.py      # Interface do sumarizador
│   └── openai_summarizer.py    # Implementação OpenAI
│
├── services/              # Serviços de negócio
│   └── document_service.py     # Serviço principal de processamento
│
├── utils/                 # Utilitários
│   ├── chunck_util.py          # Divisão de texto em chunks
│   ├── legal_metadata_extractor.py  # Extração de metadados jurídicos
│   ├── legal_prompt_builder.py      # Construtor de prompts jurídicos
│   ├── resume_validator.py          # Validador de resumos
│   └── file_utils.py               # Utilitários de arquivo
│
├── custom_types/          # Tipos customizados
│   ├── document_result.py      # Resultado do processamento
│   └── batch_result.py         # Resultado de lote
│
├── enums/                 # Enumerações
│   └── processing_status_enum.py
│
├── data/                  # Diretório de documentos (adicione seus PDFs/DOCX aqui)
│
├── main.py                # Script principal
├── config.py              # Configurações
├── requirements.txt        # Dependências
└── README.md              # Este arquivo
```

## 🏗️ Arquitetura

### Fluxo de Processamento

```
1. Leitura do Documento
   ├── PDF → PdfAdapter
   └── DOCX → DocxAdapter
   
2. Validação do Texto
   ├── Tamanho mínimo
   └── Conteúdo válido
   
3. Extração de Metadados
   ├── Número do processo
   ├── Tribunal/Comarca
   ├── Partes
   ├── Tipo de ação
   └── Tipo de documento
   
4. Construção do Prompt
   ├── Prompt base jurídico
   ├── Prompt específico por tipo
   └── Validação de metadados
   
5. Otimização do Texto
   ├── Remove espaços duplos
   └── Remove quebras desnecessárias
   
6. Divisão em Chunks (se necessário)
   ├── Chunks de 3000 palavras
   └── Preserva contexto jurídico
   
7. Processamento Paralelo
   ├── Até 5 chunks simultâneos
   └── Retry com backoff exponencial
   
8. Combinação de Resumos
   ├── Hierárquico se necessário
   └── Resumo final estruturado
   
9. Validação
   ├── Formato JSON
   ├── Campos obrigatórios
   └── Qualidade mínima
   
10. Resultado Final
    └── JSON estruturado com metadados
```

### Componentes Principais

#### `OpenAISummarizer`
- Gerencia comunicação com API OpenAI
- Implementa estratégia hierárquica para documentos grandes
- Processa chunks em paralelo
- Valida resumos gerados

#### `DocumentService`
- Orquestra o processamento completo
- Gerencia cache (em memória)
- Trata erros e validações
- Retorna resultados estruturados

#### `LegalMetadataExtractor`
- Extrai metadados jurídicos usando regex
- Identifica padrões CNJ
- Detecta tribunais, partes, tipos de ação

#### `LegalPromptBuilder`
- Constrói prompts especializados
- Adapta prompt ao tipo de documento
- Inclui instruções anti-alucinação

#### `ResumeValidator`
- Valida formato JSON
- Verifica campos obrigatórios
- Detecta informações vagas ou inventadas

## 📄 Formato de Resumo

Os resumos são retornados em formato JSON estruturado:

```json
{
  "resumo_executivo": "Resumo geral em 2-3 parágrafos com os pontos principais do documento...",
  "numero_processo": "0012197-59.2022.5.15.0135",
  "tribunal": "TJSP",
  "partes": {
    "autor": "João Silva",
    "reu": "Empresa XYZ Ltda",
    "outras_partes": []
  },
  "tipo_acao": "ação de cobrança",
  "tipo_documento": "sentença",
  "fatos_relevantes": [
    "Fato 1 descrito no documento",
    "Fato 2 descrito no documento"
  ],
  "fundamentacao": "Fundamentação jurídica resumida...",
  "decisao": "Julgamento procedente em parte...",
  "pedidos": [
    "Pedido 1",
    "Pedido 2"
  ],
  "observacoes": "Observações relevantes se houver"
}
```

### Campos por Tipo de Documento

#### Petição Inicial
- `partes` (autor, réu)
- `tipo_acao`
- `fatos_relevantes`
- `fundamentacao`
- `pedidos`

#### Sentença
- `relatorio` (resumo dos fatos)
- `fundamentacao`
- `decisao` (dispositivo - procedente/improcedente)
- `valor_condenacao` (se houver)

#### Acórdão
- `relatorio`
- `votos` (resumo dos votos)
- `fundamentacao`
- `decisao`
- `reforma` (se houve reforma)

#### Despacho
- `materia_decidida`
- `fundamentacao`
- `decisao` (deferido/indeferido)
- `prazo` (se houver)

## ⚠️ Tratamento de Erros

O sistema trata diversos tipos de erros:

### PDFs
- ✅ **Protegido por senha**: Detecta e informa claramente
- ✅ **Corrompido**: Identifica e trata graciosamente
- ✅ **Apenas imagens**: Detecta quando não há texto extraível
- ✅ **Qualidade de extração**: Valida se extraiu texto suficiente

### DOCX
- ✅ **Protegido**: Detecta arquivos protegidos
- ✅ **Corrompido**: Trata corrupção de arquivo
- ✅ **Tabelas**: Extrai texto de tabelas (importante em processos)
- ✅ **Headers/Footers**: Extrai informações de cabeçalhos e rodapés

### Texto Extraído
- ✅ **Muito curto**: Valida tamanho mínimo (10 palavras)
- ✅ **Apenas espaços**: Detecta textos inválidos
- ✅ **Qualidade**: Valida conteúdo real

### API OpenAI
- ✅ **Rate Limits**: Retry com backoff exponencial
- ✅ **Timeouts**: Tratamento de timeouts
- ✅ **Erros de API**: Mensagens de erro claras

## 🚀 Otimizações

### Otimização de Tokens

1. **Limpeza de Texto**: Remove espaços duplos, quebras desnecessárias
2. **Chunks Maiores**: 3000 palavras por chunk (reduz chamadas)
3. **Modelo Eficiente**: `gpt-4o-mini` para custos baixos
4. **Processamento Paralelo**: Até 5 chunks simultâneos

### Performance

1. **Processamento Paralelo**: Até 3 arquivos simultaneamente
2. **Cache em Memória**: Evita reprocessamento
3. **Estratégia Hierárquica**: Para documentos muito grandes
4. **Validação Prévia**: Evita processar textos inválidos

### Economia de Custos

- **Redução de ~80%** no número de chamadas (chunks maiores)
- **Redução de ~10-15%** em tokens (otimização de texto)
- **Modelo barato**: `gpt-4o-mini` vs modelos mais caros
- **Total estimado**: Redução de **60-70%** nos custos

## 🔧 Troubleshooting

### Erro: "API key da OpenAI não encontrada"

**Solução**: Certifique-se de ter criado o arquivo `.env` com:
```env
OPENAI_API_KEY=sua_chave_aqui
```

### Erro: "PDF protegido por senha"

**Causa**: O PDF está protegido e não pode ser lido sem senha.

**Solução**: 
- Remova a proteção do PDF antes de processar
- Ou use uma versão sem proteção

### Erro: "Texto extraído muito curto"

**Causa**: O documento pode estar:
- Corrompido
- Contendo apenas imagens (sem OCR)
- Vazio

**Solução**:
- Verifique se o documento abre corretamente
- Se for PDF escaneado, use OCR antes
- Verifique se o documento não está vazio

### Erro: "Resumo não está em formato JSON válido"

**Causa**: A IA pode ter retornado texto em vez de JSON.

**Solução**:
- O sistema tenta corrigir automaticamente
- Se persistir, verifique os logs para mais detalhes
- Considere usar um modelo mais recente (gpt-4o)

### Processamento muito lento

**Possíveis causas**:
- Muitos arquivos grandes
- Rate limits da API
- Conexão lenta

**Soluções**:
- Reduza `MAX_PARALLEL_FILES` em `main.py`
- Processe em lotes menores
- Verifique sua conexão com a API

### Memória insuficiente

**Causa**: Documentos muito grandes carregados em memória.

**Solução**:
- Processe documentos menores primeiro
- Considere aumentar memória disponível
- Processe um arquivo por vez (ajuste `MAX_PARALLEL_FILES = 1`)

## 📚 Documentação Técnica

### Documentos Adicionais

- **[ANALISE_CRITICA.md](ANALISE_CRITICA.md)**: Análise completa dos problemas identificados
- **[CORRECOES_IMPLEMENTADAS.md](CORRECOES_IMPLEMENTADAS.md)**: Documentação das correções implementadas

### API Reference

#### `OpenAISummarizer`

```python
summarizer = OpenAISummarizer(
    model: str = "gpt-4o-mini",
    api_key: Optional[str] = None,
    max_retries: int = 3,
    max_parallel_chunks: int = 5,
    validate_resume: bool = True
)

# Método principal
summary: str = await summarizer.summarize(text: str, prompt: Optional[str] = None)
```

#### `DocumentService`

```python
service = DocumentService(
    summarizer: BaseSummarizer,
    adapter: Optional[BaseAdapter] = None,
    enable_cache: bool = True
)

# Processar um arquivo
result: DocumentResult = await service.process_file(file_path: str)

# Processar lote
batch: BatchResult = await service.process_batch(
    file_paths: List[str],
    on_progress: Optional[Callable] = None
)
```

#### `LegalMetadataExtractor`

```python
extractor = LegalMetadataExtractor()
metadata: LegalMetadata = extractor.extract(text: str)
```

## 🤝 Contribuindo

Contribuições são bem-vindas! Para contribuir:

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📝 Licença

Este projeto é de uso interno. Todos os direitos reservados.

## 👥 Autores

- Desenvolvido para uso em escritórios de advocacia
- Especializado em processamento de documentos jurídicos brasileiros

## 🙏 Agradecimentos

- OpenAI pela API GPT
- Comunidade Python pelos pacotes utilizados
- Advogados que testaram e forneceram feedback

---

**⚠️ Importante**: Este sistema é uma ferramenta de apoio. Sempre revise os resumos gerados antes de usar em processos reais. A IA pode cometer erros ou omitir informações importantes.

**📧 Suporte**: Para problemas ou dúvidas, consulte a documentação técnica ou abra uma issue.
