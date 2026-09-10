import base64
import json
import logging
from typing import Dict, Any, List

from fastapi import HTTPException, status

from src import config
from src.pipeline import IngestionPipeline
from src.gmail_client import GmailClient
from src.exporters import ProcessedTracker
from src.schemas import WebhookPayload, WebhookResponse

logger = logging.getLogger("rag_mails.services.webhook")


def handle_gmail_webhook(payload: WebhookPayload) -> WebhookResponse:
    """
    Orquesta el flujo del Webhook:
    1. Modo Simulación Local: Procesa el texto de prueba directamente.
    2. Modo Notificación Cloud Pub/Sub: Decodifica evento, consulta correos
       autorizados en Gmail, aplica deduplicación (ProcessedTracker),
       extrae datos a Excel/JSON y marca el correo como leído.
    """
    # 1. Modo Simulación Local (curl / Swagger)
    if payload.simulate or (payload.raw_text and not payload.message):
        if not payload.raw_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El modo simulación requiere el campo 'raw_text'."
            )

        pipeline = IngestionPipeline(force_mock=bool(payload.force_mock))
        result = pipeline.process_text(
            text=payload.raw_text.strip(),
            source_file="webhook_simulacion"
        )

        if not result.success:
            return WebhookResponse(
                success=False,
                mode="simulation",
                processed_count=0,
                details=[{"error": result.error_message}],
                server_excel_path=str(config.EXCEL_OUTPUT_PATH),
                message=f"Fallo en simulación: {result.error_message}",
            )

        records_data = [r.model_dump() for r in (result.report.records if result.report else [])]
        return WebhookResponse(
            success=True,
            mode="simulation",
            processed_count=len(records_data),
            details=records_data,
            server_excel_path=str(config.EXCEL_OUTPUT_PATH),
            message="Texto simulado procesado y Excel del servidor actualizado correctamente.",
        )

    # 2. Modo Notificación de Google Cloud Pub/Sub
    pubsub_info: Dict[str, Any] = {}
    if payload.message and payload.message.data:
        try:
            decoded_bytes = base64.b64decode(payload.message.data)
            pubsub_info = json.loads(decoded_bytes.decode("utf-8"))
        except Exception as e:
            logger.warning(f"No se pudo decodificar payload Base64 de Pub/Sub: {e}")

    try:
        client = GmailClient()
        unread_emails = client.fetch_authorized_unread_emails()
    except Exception as e:
        logger.error(f"Error conectando con Gmail API: {e}")
        return WebhookResponse(
            success=False,
            mode="gmail_pubsub",
            processed_count=0,
            details=[{"error": str(e), "pubsub_info": pubsub_info}],
            server_excel_path=str(config.EXCEL_OUTPUT_PATH),
            message=f"Error consultando Gmail API: {str(e)}",
        )

    if not unread_emails:
        return WebhookResponse(
            success=True,
            mode="gmail_pubsub",
            processed_count=0,
            details=[{"status": "no_new_authorized_emails", "pubsub_info": pubsub_info}],
            server_excel_path=str(config.EXCEL_OUTPUT_PATH),
            message="Notificación recibida. No se encontraron correos no leídos del remitente autorizado.",
        )

    pipeline = IngestionPipeline(force_mock=bool(payload.force_mock))
    processed_details: List[Dict[str, Any]] = []
    tracker = ProcessedTracker()

    for email in unread_emails:
        # Control de idempotencia: si ya fue procesado antes, omitir
        if tracker.is_processed(email.id):
            logger.info(f"Correo {email.id} ya fue procesado anteriormente. Omitiendo duplicado.")
            try:
                client.mark_as_read(email.id)
            except Exception:
                pass
            processed_details.append({
                "email_id": email.id,
                "subject": email.subject,
                "sender": email.sender,
                "status": "skipped_already_processed",
                "marked_as_read": True
            })
            continue

        # Procesar con el pipeline
        res = pipeline.process_gmail_message(email)
        item_detail = {
            "email_id": email.id,
            "subject": email.subject,
            "sender": email.sender,
            "success": res.success,
        }

        if res.success:
            # Registrar en tracker de auditoría
            records_count = len(res.report.records) if res.report else 0
            tracker.record(
                email_id=email.id,
                email_date=email.date,
                sender=email.sender,
                subject=email.subject,
                records_count=records_count
            )
            try:
                client.mark_as_read(email.id)
                item_detail["marked_as_read"] = True
            except Exception as e:
                item_detail["marked_as_read"] = False
                item_detail["mark_error"] = str(e)

            if res.report:
                item_detail["records"] = [r.model_dump() for r in res.report.records]
        else:
            item_detail["error"] = res.error_message

        processed_details.append(item_detail)

    return WebhookResponse(
        success=True,
        mode="gmail_pubsub",
        processed_count=len(processed_details),
        details=processed_details,
        server_excel_path=str(config.EXCEL_OUTPUT_PATH),
        message=f"Se procesaron {len(processed_details)} correo(s) y se actualizó el Excel en el servidor.",
    )


def activate_gmail_watch(topic_name: str) -> Dict[str, Any]:
    """Registra la suscripción push de Gmail users().watch() hacia Pub/Sub."""
    try:
        client = GmailClient()
        watch_res = client.watch(topic_name=topic_name.strip())
        return {
            "success": True,
            "data": watch_res,
            "message": "Suscripción watch() activada exitosamente en Gmail API.",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al registrar watch en Gmail API: {str(e)}"
        )


def deactivate_gmail_watch() -> Dict[str, Any]:
    """Detiene las notificaciones push de Gmail."""
    try:
        client = GmailClient()
        client.stop_watch()
        return {
            "success": True,
            "message": "Notificaciones de Gmail detenidas correctamente."
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al detener watch: {str(e)}"
        )
