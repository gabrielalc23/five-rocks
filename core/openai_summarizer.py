import logging
import os
from logging import Logger
from typing import Any, Optional, List

import openai
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from core.base_summarizer import BaseSummarizer
from utils.chunck_util import chunk_text

logger: Logger = logging.getLogger(__name__)


class OpenAISummarizer(BaseSummarizer):

    def __init__(self, model: str = "gpt-5.2", api_key: Optional[str] = None):
        self.model: str = model
        self.api_key: Optional[str] = api_key or os.environ.get("OPENAI_API_KEY")

        if not self.api_key:
            raise ValueError(
                "API key da OpenAI não encontrada. "
                "Defina a variável de ambiente OPENAI_API_KEY."
            )

        self.client: AsyncOpenAI = AsyncOpenAI(api_key=self.api_key)

    async def summarize(self, text: str, prompt: Optional[str] = None) -> str:

        if not text.strip():
            return ""

        logger.debug(f"Iniciando sumarização com o modelo {self.model}.")

        try:
            chunks: List[str] = chunk_text(text)
            
            if len(chunks) == 1:
                return await self._summarize_chunk(chunks[0], prompt)

            summaries: List[str] = [await self._summarize_chunk(chunk) for chunk in chunks]
            
            combined_summaries: str = "\n".join(summaries)
            
            return await self._summarize_chunk(combined_summaries, "Combine os resumos a seguir em um único resumo coeso:")

        except openai.APIError as e:
            logger.error(f"Erro na API da OpenAI ao sumarizar: {e}")
            raise RuntimeError(f"Falha na comunicação com a API da OpenAI: {e}") from e
        except Exception as e:
            logger.error(f"Um erro inesperado ocorreu durante a sumarização: {e}")
            raise RuntimeError(f"Erro inesperado ao gerar resumo: {e}") from e

    async def _summarize_chunk(self, text: str, prompt: Optional[str] = None) -> str:
        system_prompt: str = prompt or (
            "Você é um assistente especializado em resumir documentos. "
            "Sua tarefa é criar um resumo conciso e claro do texto a seguir, "
            "capturando os pontos principais e as informações mais relevantes."
        )

        response: ChatCompletion = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            temperature=0.3,
            max_completion_tokens=250,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0,
        )

        summary: Any = response.choices[0].message.content
        logger.debug("Sumarização de trecho com OpenAI concluída com sucesso.")

        return summary.strip() if summary else ""