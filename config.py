import os
import platform
from typing import Literal

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sua_chave_de_api_aqui")

MODEL_NAME: Literal['text-davinci-003'] = "text-davinci-003"

# Detecção do sistema operacional para definir caminhos adequados
_IS_WINDOWS: bool = platform.system() == "Windows"

# Configuração do Projeto Velida 001
# Define os caminhos baseados no sistema operacional
if _IS_WINDOWS:
    # Windows: usa caminho absoluto com unidade C:
    VELIDA_INPUT_DIR: str = r"C:\Five Rocks\Velida001\A Fazer"
    VELIDA_OUTPUT_DIR: str = r"C:\Five Rocks\Velida001\Feito"
else:
    # Linux/macOS: usa caminho no diretório home do usuário
    home_dir: str = os.path.expanduser("~")
    VELIDA_INPUT_DIR: str = os.path.join(home_dir, "Five Rocks", "Velida001", "A Fazer")
    VELIDA_OUTPUT_DIR: str = os.path.join(home_dir, "Five Rocks", "Velida001", "Feito")

# Diretório padrão (mantido para compatibilidade)
DATA_DIR: Literal['data'] = "data"

# ============================================================
# PIPELINE ANTI-ALUCINACAO
# ============================================================

# Modo do pipeline: "anti_hallucination" ou "legacy"
PIPELINE_MODE: Literal['anti_hallucination', 'legacy'] = "anti_hallucination"

# Layer 1: Chunking
CHUNKER_MAX_WORDS: int = 3000

# Layer 2: Extraction
EXTRACTION_MODEL: str = "gpt-4o-mini"
EXTRACTION_MAX_PARALLEL: int = 3
EXTRACTION_TEMPERATURE: float = 0.0

# Layer 4: Consolidation
CONSOLIDATION_MODEL: str = "gpt-4o-mini"
CONSOLIDATION_TEMPERATURE: float = 0.1

# Layer 5: Generation
GENERATION_MODEL: str = "gpt-4o-mini"
GENERATION_TEMPERATURE: float = 0.2

# Layer 6: Validation
MAX_REGENERATION_ATTEMPTS: int = 2
