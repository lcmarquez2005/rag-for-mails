import json
import re
from typing import Dict, Any, Optional

from src import config
from src.services.ai.providers import (
    BaseLLMProvider,
    OllamaProvider,
    OpenAIProvider,
    GeminiProvider,
    AnthropicProvider,
)


def sanitize_json_response(response_text: str) -> Dict[str, Any]:
    """
    Limpia y repara la respuesta del LLM eliminando bloques markdown,
    espacios innecesarios o envoltorios conversacionales.
    """
    cleaned = response_text.strip()

    # Eliminar bloques markdown ```json ... ```
    if "```" in cleaned:
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', cleaned, re.IGNORECASE)
        if match:
            cleaned = match.group(1).strip()

    # Extraer bloque JSON
    json_start = cleaned.find('{')
    json_array_start = cleaned.find('[')

    if json_start != -1 and (json_array_start == -1 or json_start < json_array_start):
        json_end = cleaned.rfind('}')
        if json_end != -1:
            cleaned = cleaned[json_start:json_end + 1]
    elif json_array_start != -1:
        json_end = cleaned.rfind(']')
        if json_end != -1:
            raw_array = cleaned[json_array_start:json_end + 1]
            cleaned = f'{{"records": {raw_array}}}'

    data = json.loads(cleaned)

    if isinstance(data, dict) and "records" not in data and "machine_id" in data:
        data = {"records": [data]}
    elif isinstance(data, list):
        data = {"records": data}

    return data


PROVIDER_MAP = {
    "ollama": OllamaProvider,
    "local": OllamaProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "google": GeminiProvider,
    "anthropic": AnthropicProvider,
    "claude": AnthropicProvider,
}

SUPPORTED_PROVIDERS_CATALOG = {
    "gemini": {
        "name": "Google Gemini",
        "requires_api_key": True,
    },
    "openai": {
        "name": "OpenAI",
        "requires_api_key": True,
    },
    "anthropic": {
        "name": "Anthropic Claude",
        "requires_api_key": True,
    },
    "ollama": {
        "name": "Ollama (Local)",
        "requires_api_key": False,
    },
}


def get_provider_configured_model(provider: str) -> str:
    """Devuelve el modelo configurado en .env para el proveedor indicado."""
    norm = (provider or "").strip().lower()
    if norm in ("gemini", "google"):
        return config.GEMINI_MODEL or "gemini-flash-latest"
    elif norm in ("openai",):
        return config.OPENAI_MODEL or "gpt-4o-mini"
    elif norm in ("anthropic", "claude"):
        return config.ANTHROPIC_MODEL or "claude-3-5-sonnet-20240620"
    elif norm in ("ollama", "local"):
        return config.OLLAMA_MODEL or "qwen3:8b"
    return ""


class LLMService:
    """
    Servicio orquestador multiproveedor para extracción estructurada.
    Permite alternar de forma transparente entre Ollama, OpenAI, Gemini y Claude.
    """
    def __init__(
        self,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None,
        api_key: Optional[str] = None
    ):
        raw_provider = provider or config.LLM_PROVIDER or "ollama"
        norm_provider = (raw_provider or "ollama").strip().lower()
        if norm_provider in ("none", "null", ""):
            norm_provider = "ollama"
        elif norm_provider == "google":
            norm_provider = "gemini"
        elif norm_provider == "claude":
            norm_provider = "anthropic"
        elif norm_provider == "local":
            norm_provider = "ollama"

        self.provider_name = norm_provider

        provider_cls = PROVIDER_MAP.get(norm_provider)
        if provider_cls is None:
            if not provider or str(provider).strip().lower() in ("none", "null", ""):
                norm_provider = "ollama"
                self.provider_name = "ollama"
                provider_cls = PROVIDER_MAP.get("ollama")
            else:
                supported = ", ".join(set(PROVIDER_MAP.keys()))
                raise ValueError(f"Proveedor '{provider}' no soportado. Opciones disponibles: {supported}")

        init_kwargs = {}
        if model_name:
            init_kwargs["model"] = model_name
        elif config.LLM_MODEL and (not provider or norm_provider == config.LLM_PROVIDER):
            init_kwargs["model"] = config.LLM_MODEL
        else:
            init_kwargs["model"] = get_provider_configured_model(norm_provider)

        if temperature is not None:
            init_kwargs["temperature"] = temperature

        if norm_provider in ("ollama", "local"):
            if base_url:
                init_kwargs["base_url"] = base_url
        elif norm_provider in ("openai",):
            if api_key:
                init_kwargs["api_key"] = api_key
            if base_url:
                init_kwargs["base_url"] = base_url
        elif norm_provider in ("gemini", "google", "anthropic", "claude"):
            if api_key:
                init_kwargs["api_key"] = api_key

        self.provider: BaseLLMProvider = provider_cls(**init_kwargs)
        self.model_name = self.provider.model

    @property
    def is_online(self) -> bool:
        """Determina si el proveedor configurado está disponible."""
        return self.provider.is_available()

    def invoke_extraction(self, raw_text: str) -> Dict[str, Any]:
        """Envía el texto al proveedor configurado y devuelve el JSON saneado."""
        raw_output = self.provider.generate(raw_text)
        return sanitize_json_response(raw_output)


def get_ai_configuration():
    """Recupera la configuración actual y el catálogo de proveedores y modelos disponibles."""
    from src.schemas.api import AIConfigResponse, SupportedProviderInfo

    try:
        current_service = LLMService()
    except Exception:
        current_service = LLMService(provider="ollama")
    providers_dict = {}

    for prov_key, prov_info in SUPPORTED_PROVIDERS_CATALOG.items():
        prov_service = LLMService(provider=prov_key)
        has_key = True
        if prov_key == "gemini":
            has_key = bool(config.GEMINI_API_KEY)
        elif prov_key == "openai":
            has_key = bool(config.OPENAI_API_KEY)
        elif prov_key == "anthropic":
            has_key = bool(config.ANTHROPIC_API_KEY)

        configured_model = get_provider_configured_model(prov_key)
        # Solo se expone el modelo exacto preestablecido en el archivo .env
        configured_models = [configured_model] if configured_model else []

        providers_dict[prov_key] = SupportedProviderInfo(
            name=prov_info["name"],
            available=prov_service.is_online,
            requires_api_key=prov_info["requires_api_key"],
            has_api_key=has_key,
            default_model=configured_model,
            models=configured_models
        )

    return AIConfigResponse(
        active_provider=current_service.provider_name,
        active_model=current_service.model_name,
        is_available=current_service.is_online,
        supported_providers=providers_dict
    )


def update_ai_configuration(
    provider: str,
    model: Optional[str] = None,
    api_key: Optional[str] = None
):
    """
    Actualiza en caliente el proveedor activo.
    Usa estrictamente el modelo y clave preestablecidos en .env a menos que se indiquen explícitamente.
    """
    import os
    from src.schemas.api import UpdateAIConfigResponse

    norm_provider = provider.strip().lower()
    if norm_provider == "google":
        norm_provider = "gemini"
    elif norm_provider == "claude":
        norm_provider = "anthropic"
    elif norm_provider == "local":
        norm_provider = "ollama"

    if norm_provider not in SUPPORTED_PROVIDERS_CATALOG:
        supported = ", ".join(SUPPORTED_PROVIDERS_CATALOG.keys())
        raise ValueError(f"Proveedor '{provider}' no reconocido. Opciones válidas: {supported}")

    info = SUPPORTED_PROVIDERS_CATALOG[norm_provider]
    
    # Si no se especifica modelo, se toma estrictamente el preestablecido en .env
    selected_model = model.strip() if model and model.strip() else get_provider_configured_model(norm_provider)

    # Si se suministra API key opcional, actualizarla en memoria y entorno
    if api_key and api_key.strip():
        clean_key = api_key.strip()
        if norm_provider == "gemini":
            config.GEMINI_API_KEY = clean_key
            os.environ["GEMINI_API_KEY"] = clean_key
        elif norm_provider == "openai":
            config.OPENAI_API_KEY = clean_key
            os.environ["OPENAI_API_KEY"] = clean_key
        elif norm_provider == "anthropic":
            config.ANTHROPIC_API_KEY = clean_key
            os.environ["ANTHROPIC_API_KEY"] = clean_key

    config.LLM_PROVIDER = norm_provider
    config.LLM_MODEL = selected_model

    service = LLMService(provider=norm_provider, model_name=selected_model)
    is_avail = service.is_online

    msg = f"Proveedor cambiado exitosamente a {info['name']} con el modelo preestablecido '{selected_model}'."
    if not is_avail:
        if info["requires_api_key"]:
            msg += f" Advertencia: No se detectó API Key para {info['name']} en el .env."
        else:
            msg += " Advertencia: No se pudo conectar con el servidor Ollama."

    return UpdateAIConfigResponse(
        success=True,
        active_provider=norm_provider,
        active_model=selected_model,
        is_available=is_avail,
        message=msg
    )


# Alias de compatibilidad
OllamaService = LLMService
