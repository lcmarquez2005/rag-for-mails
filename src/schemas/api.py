from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from src.schemas.reports import MachineRecord


class ProcessTextRequest(BaseModel):
    """Solicitud para procesar texto directo de un reporte."""
    text: str = Field(
        ...,
        description="Texto no estructurado del reporte (correo, chat, etc.)",
        min_length=1
    )
    source_name: Optional[str] = Field(
        default="api_direct",
        description="Nombre o identificador de origen para trazabilidad"
    )
    force_mock: bool = Field(
        default=False,
        description="Forzar el uso del extractor determinista Mock sin llamar al LLM"
    )
    llm_provider: Optional[str] = Field(
        default=None,
        description="Proveedor de IA opcional ('ollama', 'openai', 'gemini', 'anthropic')"
    )
    llm_model: Optional[str] = Field(
        default=None,
        description="Modelo de IA específico a utilizar (ej: 'gpt-4o-mini', 'gemini-2.5-flash', 'claude-3-5-sonnet-20240620')"
    )


class ProcessTextResponse(BaseModel):
    """Respuesta con los datos extraídos y confirmación de persistencia en el servidor."""
    success: bool
    records_extracted: int
    records: List[MachineRecord] = Field(default_factory=list)
    server_excel_path: str
    server_json_path: str
    error_message: Optional[str] = None


class PubSubMessage(BaseModel):
    """Mensaje estándar de Google Cloud Pub/Sub."""
    data: Optional[str] = Field(default=None, description="Datos codificados en Base64")
    messageId: Optional[str] = Field(default=None, description="ID del mensaje en Pub/Sub")
    publishTime: Optional[str] = Field(default=None, description="Timestamp de publicación")


class WebhookPayload(BaseModel):
    """Payload soportado por el webhook de Gmail."""
    # Modo simulación directa para pruebas locales
    simulate: Optional[bool] = Field(
        default=False,
        description="Si es True, procesa directamente el raw_text sin consultar Gmail API"
    )
    raw_text: Optional[str] = Field(
        default=None,
        description="Texto de prueba a procesar en modo simulación"
    )
    force_mock: Optional[bool] = Field(
        default=False,
        description="Forzar extractor mock en modo simulación"
    )
    # Formato estándar de Google Cloud Pub/Sub Push
    message: Optional[PubSubMessage] = Field(
        default=None,
        description="Contenedor de mensaje push de Cloud Pub/Sub"
    )
    subscription: Optional[str] = Field(
        default=None,
        description="Nombre de la suscripción de Pub/Sub"
    )


class WebhookResponse(BaseModel):
    """Respuesta de confirmación del Webhook."""
    success: bool
    mode: str
    processed_count: int
    details: List[Dict[str, Any]] = Field(default_factory=list)
    server_excel_path: str
    message: str


class HealthResponse(BaseModel):
    """Estado general del servicio y dependencias."""
    status: str
    llm_provider: str = Field(default="ollama", description="Proveedor LLM activo ('ollama', 'openai', 'gemini', 'anthropic')")
    llm_model: str = Field(default="", description="Modelo LLM configurado")
    llm_available: bool = Field(default=False, description="Disponibilidad del LLM configurado")
    ollama_available: bool
    ollama_model: str
    gmail_credentials_found: bool
    gmail_token_found: bool
    server_excel_path: str
    server_json_path: str


class SupportedProviderInfo(BaseModel):
    """Información de un proveedor de IA soportado."""
    name: str
    available: bool
    requires_api_key: bool
    has_api_key: bool
    default_model: str
    models: List[str]


class AIConfigResponse(BaseModel):
    """Respuesta con la configuración activa y modelos soportados."""
    active_provider: str
    active_model: str
    is_available: bool
    supported_providers: Dict[str, SupportedProviderInfo]


class UpdateAIConfigRequest(BaseModel):
    """Solicitud para cambiar el proveedor o modelo activo."""
    provider: str = Field(
        ...,
        description="Proveedor de IA ('gemini', 'openai', 'anthropic', 'ollama')"
    )
    model: Optional[str] = Field(
        default=None,
        description="Modelo específico a activar (ej: 'gemini-1.5-pro', 'gpt-4o', etc.)"
    )
    api_key: Optional[str] = Field(
        default=None,
        description="API Key opcional para configurar el proveedor en tiempo de ejecución"
    )


class UpdateAIConfigResponse(BaseModel):
    """Respuesta de confirmación tras cambiar el proveedor o modelo."""
    success: bool
    active_provider: str
    active_model: str
    is_available: bool
    message: str
