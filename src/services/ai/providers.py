import urllib.request
from abc import ABC, abstractmethod
from typing import Optional

from src import config
from src.services.ai.prompts import (
    EXTRACTION_SYSTEM_PROMPT,
    FEW_SHOT_USER_EXAMPLE,
    FEW_SHOT_AI_EXAMPLE,
    FEW_SHOT_USER_EXAMPLE_2,
    FEW_SHOT_AI_EXAMPLE_2,
)


def is_ollama_available(url: Optional[str] = None) -> bool:
    """Verifica si el servidor local de Ollama está accesible."""
    target_url = url or config.OLLAMA_BASE_URL
    try:
        req = urllib.request.Request(f"{target_url}/api/tags", headers={"User-Agent": "rag-for-mails"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


class BaseLLMProvider(ABC):
    """Interfaz base para adaptadores de modelos de IA."""
    def __init__(self, model: str, temperature: float = 0.0):
        self.model = model
        self.temperature = temperature

    @abstractmethod
    def generate(self, input_text: str) -> str:
        """Invoca el LLM con el texto de entrada y retorna la respuesta cruda."""
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        """Comprueba si el proveedor cuenta con credenciales o conectividad activa."""
        raise NotImplementedError


class OllamaProvider(BaseLLMProvider):
    """Adaptador para Ollama (modelos locales como Qwen, Llama, DeepSeek)."""
    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None
    ):
        super().__init__(
            model=model or config.OLLAMA_MODEL,
            temperature=temperature if temperature is not None else config.OLLAMA_TEMPERATURE
        )
        self.base_url = base_url or config.OLLAMA_BASE_URL
        self._chain = None

    def is_available(self) -> bool:
        return is_ollama_available(self.base_url)

    def _get_chain(self):
        if self._chain is None:
            from langchain_ollama import OllamaLLM
            from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
            from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

            llm = OllamaLLM(
                model=self.model,
                base_url=self.base_url,
                temperature=self.temperature,
                format="json"
            )
            prompt = ChatPromptTemplate.from_messages([
                SystemMessage(content=EXTRACTION_SYSTEM_PROMPT),
                HumanMessage(content=FEW_SHOT_USER_EXAMPLE),
                AIMessage(content=FEW_SHOT_AI_EXAMPLE),
                HumanMessage(content=FEW_SHOT_USER_EXAMPLE_2),
                AIMessage(content=FEW_SHOT_AI_EXAMPLE_2),
                HumanMessagePromptTemplate.from_template("Analiza el siguiente reporte de turno y genera el JSON estructurado:\n\n{input_text}")
            ])
            self._chain = prompt | llm
        return self._chain

    def generate(self, input_text: str) -> str:
        chain = self._get_chain()
        return chain.invoke({"input_text": input_text})


class OpenAIProvider(BaseLLMProvider):
    """Adaptador para OpenAI (GPT-4o, GPT-4o-mini) y endpoints compatibles."""
    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None
    ):
        super().__init__(
            model=model or config.OPENAI_MODEL,
            temperature=temperature if temperature is not None else config.LLM_TEMPERATURE
        )
        self.api_key = api_key or config.OPENAI_API_KEY
        self.base_url = base_url or config.OPENAI_BASE_URL
        self._client = None

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client

    def generate(self, input_text: str) -> str:
        client = self._get_client()
        response = client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": FEW_SHOT_USER_EXAMPLE},
                {"role": "assistant", "content": FEW_SHOT_AI_EXAMPLE},
                {"role": "user", "content": FEW_SHOT_USER_EXAMPLE_2},
                {"role": "assistant", "content": FEW_SHOT_AI_EXAMPLE_2},
                {"role": "user", "content": f"Analiza el siguiente reporte de turno y genera el JSON estructurado:\n\n{input_text}"}
            ]
        )
        return response.choices[0].message.content or "{}"


class GeminiProvider(BaseLLMProvider):
    """Adaptador para Google Gemini (Gemini 2.5 Flash, Gemini 1.5 Pro)."""
    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: Optional[float] = None
    ):
        super().__init__(
            model=model or config.GEMINI_MODEL,
            temperature=temperature if temperature is not None else config.LLM_TEMPERATURE
        )
        self.api_key = api_key or config.GEMINI_API_KEY
        self._client = None

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _get_client(self):
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def generate(self, input_text: str) -> str:
        from google.genai import types
        client = self._get_client()

        prompt_body = (
            f"EJEMPLO 1:\n{FEW_SHOT_USER_EXAMPLE}\n{FEW_SHOT_AI_EXAMPLE}\n\n"
            f"EJEMPLO 2:\n{FEW_SHOT_USER_EXAMPLE_2}\n{FEW_SHOT_AI_EXAMPLE_2}\n\n"
            f"Analiza el siguiente reporte de turno y genera el JSON estructurado:\n\n{input_text}"
        )
        response = client.models.generate_content(
            model=self.model,
            contents=prompt_body,
            config=types.GenerateContentConfig(
                system_instruction=EXTRACTION_SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=self.temperature
            )
        )
        return response.text or "{}"


class AnthropicProvider(BaseLLMProvider):
    """Adaptador para Anthropic Claude (Claude 3.5 Sonnet, Claude 3 Haiku)."""
    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: Optional[float] = None
    ):
        super().__init__(
            model=model or config.ANTHROPIC_MODEL,
            temperature=temperature if temperature is not None else config.LLM_TEMPERATURE
        )
        self.api_key = api_key or config.ANTHROPIC_API_KEY
        self._client = None

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _get_client(self):
        if self._client is None:
            from anthropic import Anthropic
            self._client = Anthropic(api_key=self.api_key)
        return self._client

    def generate(self, input_text: str) -> str:
        client = self._get_client()
        response = client.messages.create(
            model=self.model,
            max_tokens=2048,
            temperature=self.temperature,
            system=EXTRACTION_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": FEW_SHOT_USER_EXAMPLE},
                {"role": "assistant", "content": FEW_SHOT_AI_EXAMPLE},
                {"role": "user", "content": FEW_SHOT_USER_EXAMPLE_2},
                {"role": "assistant", "content": FEW_SHOT_AI_EXAMPLE_2},
                {"role": "user", "content": f"Analiza el siguiente reporte de turno y genera el JSON estructurado:\n\n{input_text}"}
            ]
        )
        text_parts = [block.text for block in response.content if hasattr(block, "text")]
        return "\n".join(text_parts) or "{}"
