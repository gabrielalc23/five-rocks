import os
from typing import Literal

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sua_chave_de_api_aqui")

MODEL_NAME: Literal['text-davinci-003'] = "text-davinci-003"

DATA_DIR: Literal['data'] = "data"
