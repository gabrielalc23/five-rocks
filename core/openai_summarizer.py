import asyncio
import logging
import os
import re
from logging import Logger
from types import CoroutineType
from typing import Any, Optional, List, Dict

import openai
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion
from openai import RateLimitError, APIConnectionError, APIError

from asyncio import Semaphore
from core.base_summarizer import BaseSummarizer
from utils.chunck_util import chunk_text, optimize_text
from utils.legal_metadata_extractor import LegalMetadataExtractor, LegalMetadata
from utils.legal_prompt_builder import LegalPromptBuilder
from utils.resume_validator import ResumeValidator

logger: Logger = logging.getLogger(__name__)


class OpenAISummarizer(BaseSummarizer):
    def __init__(
        self, 
        model: str = "gpt-4o-mini", 
        api_key: Optional[str] = None,
        max_retries: int = 3,
        max_parallel_chunks: int = 2,
        validate_resume: bool = True
    ):
        self.model: str = model
        self.api_key: Optional[str] = api_key or os.environ.get("OPENAI_API_KEY")
        self.max_retries: int = max_retries
        self.max_parallel_chunks: int = max_parallel_chunks
        self.validate_resume: bool = validate_resume

        if not self.api_key:
            raise ValueError(
                "API key da OpenAI não encontrada. "
                "Defina a variável de ambiente OPENAI_API_KEY."
            )

        self.client: AsyncOpenAI = AsyncOpenAI(api_key=self.api_key)
        
        self.metadata_extractor: LegalMetadataExtractor = LegalMetadataExtractor()
        self.prompt_builder: LegalPromptBuilder = LegalPromptBuilder()
        self.resume_validator: ResumeValidator = ResumeValidator()

    async def summarize(self, text: str, prompt: Optional[str] = None) -> str:
        if not text.strip():
            return ""

        logger.debug("Extraindo metadados jurídicos...")
        metadata: LegalMetadata = self.metadata_extractor.extract(text)
        logger.debug(f"Metadados extraídos: processo={metadata.process_number}, "
                    f"tribunal={metadata.tribunal}, tipo={metadata.tipo_documento}")

        optimized_text: str = optimize_text(text)
        
        logger.debug(f"Iniciando sumarização com o modelo {self.model}.")
        logger.debug(f"Texto original: {len(text)} chars, Otimizado: {len(optimized_text)} chars")

        try:
            legal_prompt: str = self.prompt_builder.build_prompt(
                document_type=metadata.tipo_documento,
                metadata=metadata
            )
            chunks: List[str] = chunk_text(optimized_text, max_words=5000)
            
            if len(chunks) == 1:
                summary = await self._summarize_chunk_with_retry(chunks[0], legal_prompt)
            else:
                logger.info(f"Processando {len(chunks)} chunks em paralelo (máx {self.max_parallel_chunks} simultâneos)")
                summaries: List[str] = await self._process_chunks_parallel(chunks, legal_prompt)
                
                combined_summaries: str = "\n\n".join(summaries)
                
                if len(combined_summaries.split()) > 2000:
                    logger.info("Resumo combinado ainda muito grande, aplicando resumo hierárquico")
                    summary = await self._hierarchical_summarize(combined_summaries, legal_prompt)
                else:
                    final_prompt: str = (
                        "Combine os resumos a seguir em um único resumo coeso e completo em formato JSON. "
                        "Mantenha todas as informações importantes de cada resumo. "
                        "O resultado deve ser um resumo profissional e detalhado em JSON válido."
                    )
                    summary = await self._summarize_chunk_with_retry(combined_summaries, final_prompt)
            
            if self.validate_resume:
                is_valid, error, validated_data = self.resume_validator.validate(summary)
                if not is_valid:
                    logger.warning(f"Resumo não passou na validação: {error}")
                    if validated_data:
                        if metadata.process_number and not validated_data.get('numero_processo'):
                            validated_data['numero_processo'] = metadata.process_number
                        if metadata.tribunal and not validated_data.get('tribunal'):
                            validated_data['tribunal'] = metadata.tribunal
                        import json
                        summary: str = json.dumps(validated_data, ensure_ascii=False, indent=2)
                    else:
                        logger.error(f"Resumo inválido e não foi possível corrigir: {error}")
                else:
                    logger.debug("Resumo validado com sucesso")
            
            return summary

        except openai.APIError as e:
            logger.error(f"Erro na API da OpenAI ao sumarizar: {e}")
            raise RuntimeError(f"Falha na comunicação com a API da OpenAI: {e}") from e
        except Exception as e:
            logger.error(f"Um erro inesperado ocorreu durante a sumarização: {e}")
            raise RuntimeError(f"Erro inesperado ao gerar resumo: {e}") from e

    async def _process_chunks_parallel(self, chunks: List[str], prompt: Optional[str] = None) -> List[str]:
        semaphore: Semaphore = asyncio.Semaphore(self.max_parallel_chunks)
        
        async def process_with_semaphore(chunk: str, index: int) -> str:
            async with semaphore:
                logger.debug(f"Processando chunk {index + 1}/{len(chunks)}")
                if index > 0:
                    await asyncio.sleep(0.5)
                return await self._summarize_chunk_with_retry(chunk, prompt)
        
        tasks: List[CoroutineType[Any, Any, str]] = [process_with_semaphore(chunk, i) for i, chunk in enumerate(chunks)]
        summaries: List[str] = await asyncio.gather(*tasks)
        return summaries

    async def _hierarchical_summarize(self, text: str, prompt: Optional[str] = None) -> str:
        words: List[str] = text.split()
        group_size: int = 1500 
        groups: List[str] = [
            " ".join(words[i:i + group_size])
            for i in range(0, len(words), group_size)
        ]
        
        logger.info(f"Aplicando resumo hierárquico em {len(groups)} grupos")
        
        group_summaries: List[str] = await self._process_chunks_parallel(groups, prompt)
        
        combined_summaries: str = "\n\n".join(group_summaries)
        final_prompt: str = prompt or (
            "Crie um resumo completo e detalhado em formato JSON do seguinte texto, "
            "mantendo todas as informações importantes e seguindo a estrutura JSON definida."
        )
        return await self._summarize_chunk_with_retry(combined_summaries, final_prompt)

    async def _summarize_chunk_with_retry(
        self, 
        text: str, 
        prompt: Optional[str] = None
    ) -> str:
        for attempt in range(self.max_retries):
            try:
                return await self._summarize_chunk(text, prompt)
            except (RateLimitError, APIConnectionError) as e:
                if attempt == self.max_retries - 1:
                    raise
                wait_time: float = (2 ** attempt) + (attempt * 0.5)
                logger.warning(f"Erro na API (tentativa {attempt + 1}/{self.max_retries}): {e}. Aguardando {wait_time:.1f}s...")
                await asyncio.sleep(wait_time)
            except APIError as e:
                logger.error(f"Erro na API da OpenAI: {e}")
                raise
        
        return ""

    async def _summarize_chunk(self, text: str, prompt: Optional[str] = None) -> str:
        system_prompt: str = prompt or self.prompt_builder.get_default_prompt()

        request_params: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            "temperature": 0.1, 
            "max_tokens": 3000, 
            "top_p": 0.9,  
            "frequency_penalty": 0.2,
            "presence_penalty": 0.1,
        }
        
        if "json" in system_prompt.lower() and ("gpt-4o" in self.model or "gpt-4-turbo" in self.model):
            request_params["response_format"] = {"type": "json_object"}
        
        response: ChatCompletion = await self.client.chat.completions.create(**request_params)

        summary: Any = response.choices[0].message.content
        logger.debug("Sumarização de trecho com OpenAI concluída com sucesso.")

        return summary.strip() if summary else ""