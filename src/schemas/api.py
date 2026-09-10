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
        description="Forzar el uso del extractor determinista Mock sin llamar a Ollama"
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
    ollama_available: bool
    ollama_model: str
    gmail_credentials_found: bool
    gmail_token_found: bool
    server_excel_path: str
    server_json_path: str
