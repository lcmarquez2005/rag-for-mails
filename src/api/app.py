from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

from src.schemas import (
    ProcessTextRequest,
    ProcessTextResponse,
    WebhookPayload,
    WebhookResponse,
    HealthResponse,
)
from src.services.health_service import check_system_health
from src.services.report_service import process_text_report
from src.services.webhook_service import (
    handle_gmail_webhook,
    activate_gmail_watch,
    deactivate_gmail_watch,
)

# ==============================================================================
# 1. INICIALIZACIÓN DE LA APLICACIÓN FASTAPI
# ==============================================================================
app = FastAPI(
    title="RAG for Mails API",
    description="Servicio API para la extracción automatizada de reportes de moldeo y recepción de Webhooks de Gmail.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# 2. ENDPOINTS (DELEGADOS A LA CAPA DE SERVICIOS)
# ==============================================================================
@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Estado del servicio y dependencias",
    tags=["Sistema"]
)
def health_check():
    """Verifica el estado del servicio, Ollama y persistencia en el servidor."""
    return check_system_health()


@app.post(
    "/api/v1/process/text",
    response_model=ProcessTextResponse,
    summary="Procesar texto no estructurado de reporte",
    tags=["Procesamiento"]
)
def process_text_endpoint(payload: ProcessTextRequest):
    """Extrae datos de producción desde texto y actualiza Excel/JSON en el servidor."""
    return process_text_report(payload)


@app.post(
    "/api/v1/webhook/gmail",
    response_model=WebhookResponse,
    status_code=status.HTTP_200_OK,
    summary="Webhook para notificaciones push de Gmail",
    tags=["Webhook Gmail"]
)
def gmail_webhook_endpoint(payload: WebhookPayload):
    """Maneja la notificación push de Gmail (Cloud Pub/Sub) o simulación local con deduplicación."""
    return handle_gmail_webhook(payload)


@app.post(
    "/api/v1/webhook/gmail/watch",
    summary="Activar suscripción watch() de Gmail hacia Pub/Sub",
    tags=["Webhook Gmail"]
)
def register_gmail_watch_endpoint(topic_name: str):
    """Registra la suscripción watch() en Gmail hacia el Topic de Pub/Sub especificado."""
    return activate_gmail_watch(topic_name)


@app.post(
    "/api/v1/webhook/gmail/stop-watch",
    summary="Detener suscripción watch() de Gmail",
    tags=["Webhook Gmail"]
)
def stop_gmail_watch_endpoint():
    """Detiene las notificaciones push de Gmail."""
    return deactivate_gmail_watch()
