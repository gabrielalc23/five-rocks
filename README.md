# Five Rocks

Sistema de sumarização inteligente de documentos jurídicos brasileiros utilizando IA (OpenAI GPT). Desenvolvido para advogados e profissionais do direito que precisam processar grandes volumes de documentos processuais de forma eficiente.

## Sumario

- [Sobre o Projeto](#sobre-o-projeto)
- [Funcionalidades](#funcionalidades)
- [Requisitos](#requisitos)
- [Instalacao](#instalacao)
- [Configuracao](#configuracao)
- [Como Usar](#como-usar)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Arquitetura](#arquitetura)
- [Formato dos Resumos](#formato-dos-resumos)
- [Tratamento de Erros](#tratamento-de-erros)
- [Solucao de Problemas](#solucao-de-problemas)
- [API Reference](#api-reference)

---

## Sobre o Projeto

O Five Rocks e um bot especializado em resumir documentos juridicos brasileiros, incluindo:

- Peticoes iniciais
- Sentencas
- Acordaos
- Despachos
- Outros documentos processuais

O sistema utiliza a API da OpenAI com prompts otimizados para o contexto juridico brasileiro, extraindo automaticamente metadados como numero do processo (padrao CNJ), partes envolvidas, tribunal e tipo de acao.

---

## Funcionalidades

### Processamento de Documentos
- Suporte a arquivos PDF e DOCX
- Processamento assincrono e paralelo
- Tratamento de documentos grandes (2000+ paginas)
- Estrategia hierarquica de sumarizacao para textos extensos

### Inteligencia Juridica
- Prompts especializados por tipo de documento
- Extracao automatica de metadados juridicos
- Identificacao de padroes CNJ para numeros de processo
- Deteccao automatica de tribunais e comarcas

### Qualidade e Confiabilidade
- Validacao automatica dos resumos gerados
- Tratamento robusto de erros (PDFs protegidos, corrompidos, etc.)
- Retry com backoff exponencial para rate limits
- Cache em memoria para evitar reprocessamento

### Otimizacao de Custos
- Uso do modelo `gpt-4o-mini` por padrao
- Otimizacao de tokens (limpeza de texto)
- Chunks maiores para reduzir chamadas a API
- Reducao estimada de 60-70% nos custos

---

## Requisitos

- Python 3.10 ou superior
- Chave de API da OpenAI
- Conexao com a internet

---

## Instalacao

### 1. Clone o repositorio

```bash
git clone <url-do-repositorio>
cd five-rocks
```

### 2. Crie e ative um ambiente virtual

```bash
# Linux/macOS
python3 -m venv .venv
source .venv/bin/activate

# Windows
python -m venv .venv
.venv\Scripts\activate
```

### 3. Instale as dependencias

```bash
pip install -r requirements.txt
```

### 4. Configure as variaveis de ambiente

Crie um arquivo `.env` na raiz do projeto:

```bash
OPENAI_API_KEY=sua_chave_da_openai_aqui
```

---

## Configuracao

### Variaveis de Ambiente

| Variavel | Descricao | Obrigatorio |
|----------|-----------|-------------|
| `OPENAI_API_KEY` | Chave de API da OpenAI | Sim |

### Arquivo de Configuracao (config.py)

```python
DATA_DIR = "data"  # Diretorio onde os documentos serao lidos
MODEL_NAME = "text-davinci-003"  # Modelo padrao (sobrescrito pelo sumarizador)
```

### Configuracao do Sumarizador

O sumarizador pode ser configurado com os seguintes parametros:

```python
from core.openai_summarizer import OpenAISummarizer

summarizer = OpenAISummarizer(
    model="gpt-4o-mini",      # Modelo a ser usado
    max_retries=3,            # Tentativas em caso de falha
    max_parallel_chunks=5,    # Chunks processados em paralelo
    validate_resume=True      # Validar resumos gerados
)
```

---

## Como Usar

### Uso via Linha de Comando

1. Coloque seus documentos PDF ou DOCX na pasta `data/`

2. Execute o script principal:

```bash
python main.py
```

3. Acompanhe o processamento no terminal:

```
============================================================
 BOT DE SUMARIZACAO DE PROCESSOS (ASYNC)
============================================================

Encontrados: 5 arquivo(s) para processar (3 PDF(s), 2 DOCX(s))

  [1/5] ✓ processo_001.pdf
  [2/5] ✓ processo_002.docx
  [3/5] ✗ processo_003.pdf (PDF protegido por senha)
  [4/5] ✓ processo_004.pdf
  [5/5] ✓ processo_005.docx

============================================================
 RESULTADOS - TODOS OS ARQUIVOS
============================================================

Processados: 5 | Sucesso: 4 | Erros: 1 | Taxa: 80.0%

Resumos gerados:
----------------------------------------
▶ processo_001.pdf
  Palavras: 15234 | Tempo: 21792ms
  {"resumo_executivo": "...", ...}
```

### Uso Programatico

```python
import asyncio
from adapters import PdfAdapter, DocxAdapter
from core.openai_summarizer import OpenAISummarizer
from services.document_service import DocumentService

async def processar_documento():
    # Inicializa componentes
    summarizer = OpenAISummarizer()
    adapter = PdfAdapter()  # ou DocxAdapter() para arquivos .docx

    # Cria servico de documentos
    service = DocumentService(
        adapter=adapter,
        summarizer=summarizer
    )

    # Processa um arquivo
    result = await service.process_file("data/meu_processo.pdf")

    if result.is_success:
        print(f"Resumo: {result.summary}")
        print(f"Palavras no documento: {result.word_count}")
        print(f"Tempo de processamento: {result.processing_time_ms}ms")
    else:
        print(f"Erro: {result.error_message}")

# Executa
asyncio.run(processar_documento())
```

### Processamento em Lote

```python
from custom_types.batch_result import BatchResult

async def processar_lote():
    service = DocumentService(adapter=PdfAdapter(), summarizer=OpenAISummarizer())

    arquivos = [
        "data/processo_001.pdf",
        "data/processo_002.pdf",
        "data/processo_003.pdf"
    ]

    batch: BatchResult = await service.process_batch(
        file_paths=arquivos,
        on_progress=lambda r, i, t: print(f"[{i}/{t}] {r.file_name}")
    )

    print(batch.summary())  # Processados: 3 | Sucesso: 3 | Erros: 0
```

---

## Estrutura do Projeto

```
five-rocks/
│
├── adapters/                    # Adaptadores para leitura de documentos
│   ├── __init__.py
│   ├── base_adapter.py          # Interface base para adaptadores
│   ├── pdf_adapter.py           # Leitor de arquivos PDF
│   └── docx_adapter.py          # Leitor de arquivos DOCX
│
├── builders/                    # Construtores
│   └── ...
│
├── constants/                   # Constantes do sistema
│   └── ...
│
├── core/                        # Nucleo do sistema
│   ├── __init__.py
│   ├── base_summarizer.py       # Interface base do sumarizador
│   └── openai_summarizer.py     # Implementacao com OpenAI
│
├── custom_types/                # Tipos customizados
│   ├── __init__.py
│   ├── document_result.py       # Resultado do processamento
│   └── batch_result.py          # Resultado de lote
│
├── decorators/                  # Decoradores utilitarios
│   └── ...
│
├── enums/                       # Enumeracoes
│   └── processing_status_enum.py
│
├── info/                        # Informacoes e documentacao
│   └── ...
│
├── modules/                     # Modulos auxiliares
│   └── ...
│
├── services/                    # Servicos de negocio
│   ├── __init__.py
│   └── document_service.py      # Servico principal
│
├── utils/                       # Utilitarios
│   ├── __init__.py
│   ├── chunck_util.py           # Divisao de texto em chunks
│   ├── file_utils.py            # Utilitarios de arquivo
│   ├── legal_metadata_extractor.py  # Extrator de metadados
│   ├── legal_prompt_builder.py      # Construtor de prompts
│   └── resume_validator.py          # Validador de resumos
│
├── data/                        # Diretorio para documentos (gitignore)
│
├── main.py                      # Ponto de entrada principal
├── config.py                    # Configuracoes do sistema
├── requirements.txt             # Dependencias Python
├── .env                         # Variaveis de ambiente (gitignore)
├── .gitignore                   # Arquivos ignorados pelo Git
└── README.md                    # Este arquivo
```

---

## Arquitetura

### Fluxo de Processamento

```
┌─────────────────────────────────────────────────────────────────┐
│                     FLUXO DE PROCESSAMENTO                       │
└─────────────────────────────────────────────────────────────────┘

   ┌──────────┐     ┌──────────┐     ┌──────────────────┐
   │   PDF    │────>│ Adapter  │────>│ Texto Extraido   │
   │   DOCX   │     │          │     │                  │
   └──────────┘     └──────────┘     └────────┬─────────┘
                                              │
                                              v
                                   ┌──────────────────┐
                                   │    Validacao     │
                                   │  (tamanho min.)  │
                                   └────────┬─────────┘
                                              │
                                              v
                                   ┌──────────────────┐
                                   │    Extracao de   │
                                   │    Metadados     │
                                   └────────┬─────────┘
                                              │
                                              v
                                   ┌──────────────────┐
                                   │   Construcao do  │
                                   │     Prompt       │
                                   └────────┬─────────┘
                                              │
                                              v
                                   ┌──────────────────┐
                                   │   Divisao em     │
                                   │    Chunks        │
                                   └────────┬─────────┘
                                              │
                                              v
                                   ┌──────────────────┐
                                   │  Processamento   │
                                   │   Paralelo       │
                                   │   (OpenAI API)   │
                                   └────────┬─────────┘
                                              │
                                              v
                                   ┌──────────────────┐
                                   │   Combinacao de  │
                                   │    Resumos       │
                                   └────────┬─────────┘
                                              │
                                              v
                                   ┌──────────────────┐
                                   │    Validacao     │
                                   │     Final        │
                                   └────────┬─────────┘
                                              │
                                              v
                                   ┌──────────────────┐
                                   │  JSON Estruturado│
                                   │   com Metadados  │
                                   └──────────────────┘
```

### Componentes Principais

#### OpenAISummarizer
Responsavel pela comunicacao com a API da OpenAI. Implementa:
- Estrategia hierarquica para documentos grandes
- Processamento paralelo de chunks
- Validacao de resumos gerados
- Retry com backoff exponencial

#### DocumentService
Orquestra todo o fluxo de processamento:
- Coordena adapters e sumarizador
- Gerencia cache em memoria
- Trata erros e validacoes
- Retorna resultados estruturados

#### LegalMetadataExtractor
Extrai metadados juridicos do texto usando regex:
- Numeros de processo (padrao CNJ)
- Tribunais e comarcas
- Partes (autor, reu)
- Tipo de acao e documento

#### LegalPromptBuilder
Constroi prompts especializados para cada tipo de documento:
- Prompts base para contexto juridico
- Prompts especificos por tipo (peticao, sentenca, etc.)
- Instrucoes anti-alucinacao

---

## Formato dos Resumos

Os resumos sao retornados em formato JSON estruturado:

```json
{
  "resumo_executivo": "Resumo geral do documento em 2-3 paragrafos...",
  "numero_processo": "0012197-59.2022.5.15.0135",
  "tribunal": "TRT 15a Regiao",
  "partes": {
    "autor": "Joao da Silva",
    "reu": "Empresa ABC Ltda",
    "outras_partes": ["Sindicato dos Trabalhadores"]
  },
  "tipo_acao": "Reclamacao Trabalhista",
  "tipo_documento": "Sentenca",
  "fatos_relevantes": [
    "Autor alega ter sido dispensado sem justa causa",
    "Periodo de trabalho: 01/2020 a 12/2022"
  ],
  "fundamentacao": "Resumo da fundamentacao juridica...",
  "decisao": "Julgou PROCEDENTE EM PARTE os pedidos...",
  "pedidos": [
    "Verbas rescisorias",
    "Horas extras",
    "Danos morais"
  ],
  "observacoes": "Prazo para recurso: 8 dias"
}
```

### Campos por Tipo de Documento

| Tipo | Campos Especificos |
|------|-------------------|
| Peticao Inicial | `partes`, `tipo_acao`, `fatos_relevantes`, `fundamentacao`, `pedidos` |
| Sentenca | `relatorio`, `fundamentacao`, `decisao`, `valor_condenacao` |
| Acordao | `relatorio`, `votos`, `fundamentacao`, `decisao`, `reforma` |
| Despacho | `materia_decidida`, `fundamentacao`, `decisao`, `prazo` |

---

## Tratamento de Erros

### Erros de Documento

| Tipo | Descricao | Tratamento |
|------|-----------|------------|
| PDF protegido | Arquivo com senha | Detecta e informa ao usuario |
| PDF corrompido | Arquivo danificado | Tratamento gracioso com mensagem clara |
| PDF so imagem | Sem texto extraivel | Detecta e sugere OCR |
| DOCX protegido | Arquivo com protecao | Detecta e informa |
| Texto curto | Menos de 10 palavras | Valida e rejeita |

### Erros de API

| Tipo | Descricao | Tratamento |
|------|-----------|------------|
| Rate Limit | Limite de requisicoes | Retry com backoff exponencial |
| Timeout | Tempo excedido | Retry automatico |
| Erro de rede | Falha de conexao | Mensagem de erro clara |

---

## Solucao de Problemas

### "API key da OpenAI nao encontrada"

Certifique-se de que o arquivo `.env` existe e contem:
```
OPENAI_API_KEY=sk-sua-chave-aqui
```

### "PDF protegido por senha"

O PDF esta protegido. Opcoes:
- Remova a protecao do PDF usando ferramentas como Adobe Acrobat ou qpdf
- Use uma versao sem protecao do documento

### "Texto extraido muito curto"

Possiveis causas:
- Documento corrompido
- PDF escaneado sem OCR
- Documento vazio

Solucoes:
- Verifique se o documento abre corretamente
- Para PDFs escaneados, aplique OCR antes (use ferramentas como ocrmypdf)

### "Resumo nao esta em formato JSON valido"

O sistema tenta corrigir automaticamente. Se persistir:
- Verifique os logs para detalhes
- Considere usar um modelo mais capaz (gpt-4o)

### Processamento muito lento

Ajuste o paralelismo em `main.py`:
```python
MAX_PARALLEL_FILES = 1  # Reduza se houver rate limits
```

### Memoria insuficiente

Para documentos muito grandes:
```python
MAX_PARALLEL_FILES = 1  # Processe um arquivo por vez
```

---

## API Reference

### OpenAISummarizer

```python
class OpenAISummarizer:
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        max_retries: int = 3,
        max_parallel_chunks: int = 5,
        validate_resume: bool = True
    )

    async def summarize(
        self,
        text: str,
        prompt: Optional[str] = None
    ) -> str:
        """
        Gera um resumo do texto fornecido.

        Args:
            text: Texto a ser resumido
            prompt: Prompt customizado (opcional)

        Returns:
            Resumo em formato JSON string
        """
```

### DocumentService

```python
class DocumentService:
    def __init__(
        self,
        summarizer: BaseSummarizer,
        adapter: Optional[BaseAdapter] = None,
        enable_cache: bool = True
    )

    async def process_file(
        self,
        file_path: str
    ) -> DocumentResult:
        """
        Processa um unico arquivo.

        Args:
            file_path: Caminho para o arquivo PDF ou DOCX

        Returns:
            DocumentResult com resumo ou erro
        """

    async def process_batch(
        self,
        file_paths: List[str],
        on_progress: Optional[Callable] = None
    ) -> BatchResult:
        """
        Processa multiplos arquivos.

        Args:
            file_paths: Lista de caminhos
            on_progress: Callback para progresso

        Returns:
            BatchResult com todos os resultados
        """
```

### DocumentResult

```python
@dataclass
class DocumentResult:
    file_name: str           # Nome do arquivo
    is_success: bool         # Se processou com sucesso
    summary: Optional[str]   # Resumo JSON ou None
    word_count: int          # Contagem de palavras
    processing_time_ms: float  # Tempo de processamento
    error_message: Optional[str]  # Mensagem de erro ou None
```

### BatchResult

```python
@dataclass
class BatchResult:
    results: List[DocumentResult]

    def summary(self) -> str:
        """Retorna resumo estatistico do lote"""

    def get_successful(self) -> List[DocumentResult]:
        """Retorna apenas resultados bem-sucedidos"""

    def get_errors(self) -> List[DocumentResult]:
        """Retorna apenas resultados com erro"""
```

---

## Dependencias

- `python-docx` - Leitura de arquivos DOCX
- `pypdf` - Leitura de arquivos PDF
- `openai` - API da OpenAI
- `anthropic` - API da Anthropic (preparado para uso futuro)
- `python-dotenv` - Gerenciamento de variaveis de ambiente
- `numpy` - Operacoes numericas
- `pandas` - Manipulacao de dados
- `faiss-cpu` - Vector store para busca semantica

---

## Aviso Importante

Este sistema e uma ferramenta de apoio ao trabalho juridico. **Sempre revise os resumos gerados antes de utiliza-los em processos reais.** A inteligencia artificial pode cometer erros ou omitir informacoes importantes.

---

## Licenca

Todos os direitos reservados.
