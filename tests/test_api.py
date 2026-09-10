import base64
import json
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from src.api.app import app
from src.gmail_client import GmailMessage

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "llm_provider" in data
    assert "llm_available" in data
    assert "ollama_available" in data
    assert "server_excel_path" in data
    assert "server_json_path" in data


def test_process_text_json():
    payload = {
        "text": "Actualización del Turno 1:\nLa máquina M102 estuvo detenida durante 45 minutos debido a un cambio de molde. Total de piezas aprobadas: 1200. Piezas rechazadas: 15.\nLíder de turno: Juan Pérez.",
        "force_mock": True,
        "source_name": "test_direct_json"
    }
    response = client.post("/api/v1/process/text", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["records_extracted"] == 1
    assert data["records"][0]["machine_id"] == "M102"
    assert data["records"][0]["approved_parts"] == 1200
    assert data["records"][0]["rejected_parts"] == 15
    assert data["records"][0]["shift_leader"] == "Juan Pérez"
    assert "server_excel_path" in data


def test_process_text_secondary():
    payload = {
        "text": "Turno 2:\nMáquina M105: 850 piezas aprobadas, 95 rechazadas por rebaba. Paro de 75 minutos.\nLíder: Maria Rodriguez",
        "force_mock": True,
        "source_name": "test_secondary"
    }
    response = client.post("/api/v1/process/text", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["records_extracted"] == 1
    assert data["records"][0]["machine_id"] == "M105"
    assert data["records"][0]["approved_parts"] == 850


def test_process_text_empty():
    response = client.post("/api/v1/process/text", json={"text": "   "})
    assert response.status_code == 400


def test_webhook_simulation_mode():
    payload = {
        "simulate": True,
        "raw_text": "Turno 1:\nMáquina M102 detenida 30 min por ajuste térmico. 500 piezas aprobadas, 10 rechazadas.\nLíder: Carlos Santana",
        "force_mock": True
    }
    response = client.post("/api/v1/webhook/gmail", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["mode"] == "simulation"
    assert data["processed_count"] == 1
    assert len(data["details"]) == 1
    assert data["details"][0]["machine_id"] == "M102"
    assert data["details"][0]["approved_parts"] == 500


def test_webhook_pubsub_mode_with_unread_emails():
    pubsub_data = base64.b64encode(json.dumps({
        "emailAddress": "l23200286@pachuca.tecnm.mx",
        "historyId": "999888"
    }).encode("utf-8")).decode("utf-8")

    fake_email = GmailMessage(
        id="gmail_pubsub_1",
        thread_id="th_pubsub_1",
        sender="l23200286@pachuca.tecnm.mx",
        recipient="me@domain.com",
        subject="Reporte M102",
        date="2026-09-10",
        snippet="M102",
        body="Máquina M102: 1200 piezas aprobadas, 15 rechazadas, 45 min paro por cambio de molde. Líder: Juan Pérez."
    )

    with patch("src.services.webhook_service.GmailClient") as mock_gmail_cls:
        mock_instance = MagicMock()
        mock_instance.fetch_authorized_unread_emails.return_value = [fake_email]
        mock_gmail_cls.return_value = mock_instance

        payload = {
            "message": {
                "data": pubsub_data,
                "messageId": "msg_sub_123"
            },
            "force_mock": True
        }

        response = client.post("/api/v1/webhook/gmail", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["mode"] == "gmail_pubsub"
        assert data["processed_count"] == 1
        assert data["details"][0]["marked_as_read"] is True
        mock_instance.mark_as_read.assert_called_once_with("gmail_pubsub_1")


def test_webhook_pubsub_mode_no_emails():
    with patch("src.services.webhook_service.GmailClient") as mock_gmail_cls:
        mock_instance = MagicMock()
        mock_instance.fetch_authorized_unread_emails.return_value = []
        mock_gmail_cls.return_value = mock_instance

        payload = {
            "message": {
                "data": "e30=",
                "messageId": "empty_msg"
            }
        }

        response = client.post("/api/v1/webhook/gmail", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["processed_count"] == 0
        assert "No se encontraron correos no leídos" in data["message"]


def test_gmail_watch_endpoints():
    with patch("src.services.webhook_service.GmailClient") as mock_gmail_cls:
        mock_instance = MagicMock()
        mock_instance.watch.return_value = {"historyId": "12345", "expiration": "1700000000"}
        mock_gmail_cls.return_value = mock_instance

        resp = client.post("/api/v1/webhook/gmail/watch?topic_name=projects/test-p/topics/test-t")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        mock_instance.watch.assert_called_once_with(topic_name="projects/test-p/topics/test-t")

        resp_stop = client.post("/api/v1/webhook/gmail/stop-watch")
        assert resp_stop.status_code == 200
        assert resp_stop.json()["success"] is True
        mock_instance.stop_watch.assert_called_once()


def test_webhook_idempotency_skips_duplicate_email():
    from src.exporters import ProcessedTracker

    fake_email = GmailMessage(
        id="already_processed_msg_id",
        thread_id="th_dup",
        sender="l23200286@pachuca.tecnm.mx",
        recipient="me@domain.com",
        subject="Reporte M102",
        date="2026-09-10",
        snippet="M102",
        body="Máquina M102: 1200 piezas aprobadas. Líder: Juan Pérez."
    )

    tracker = ProcessedTracker()
    tracker.record(email_id="already_processed_msg_id")

    with patch("src.services.webhook_service.GmailClient") as mock_gmail_cls:
        mock_instance = MagicMock()
        mock_instance.fetch_authorized_unread_emails.return_value = [fake_email]
        mock_gmail_cls.return_value = mock_instance

        payload = {
            "message": {
                "data": "e30=",
                "messageId": "msg_dup_123"
            },
            "force_mock": True
        }

        response = client.post("/api/v1/webhook/gmail", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["details"]) == 1
        assert data["details"][0]["status"] == "skipped_already_processed"
        mock_instance.mark_as_read.assert_called_once_with("already_processed_msg_id")


def test_process_text_with_llm_provider_param():
    payload = {
        "text": "Turno 1: Máquina M102 con 500 piezas aprobadas. Líder: Carlos Santana",
        "force_mock": True,
        "llm_provider": "gemini",
        "llm_model": "gemini-2.5-flash"
    }
    response = client.post("/api/v1/process/text", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["records_extracted"] == 1
    assert data["records"][0]["machine_id"] == "M102"


def test_get_ai_models_endpoint():
    response = client.get("/api/v1/ai/models")
    assert response.status_code == 200
    data = response.json()
    assert "active_provider" in data
    assert "active_model" in data
    assert "supported_providers" in data
    assert "gemini" in data["supported_providers"]
    assert "openai" in data["supported_providers"]
    assert "anthropic" in data["supported_providers"]
    assert "ollama" in data["supported_providers"]

    gemini_info = data["supported_providers"]["gemini"]
    assert gemini_info["name"] == "Google Gemini"
    assert len(gemini_info["models"]) == 1
    assert gemini_info["models"][0] == gemini_info["default_model"]


def test_update_ai_models_endpoint_success():
    payload = {
        "provider": "gemini",
        "model": "gemini-1.5-pro",
        "api_key": "AIzaSyFakeKeyForTesting123"
    }
    response = client.post("/api/v1/ai/models", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["active_provider"] == "gemini"
    assert data["active_model"] == "gemini-1.5-pro"
    assert data["is_available"] is True

    # Confirm GET reflects the updated configuration
    get_resp = client.get("/api/v1/ai/models")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["active_provider"] == "gemini"
    assert get_data["active_model"] == "gemini-1.5-pro"


def test_update_ai_models_endpoint_provider_only():
    # Enviar solo 'provider' debe usar el modelo preestablecido en .env
    response = client.post("/api/v1/ai/models", json={"provider": "ollama"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["active_provider"] == "ollama"
    assert data["active_model"] == "qwen3:8b"

    # Cambiar a gemini enviando solo provider
    resp_gemini = client.post("/api/v1/ai/models", json={"provider": "gemini"})
    assert resp_gemini.status_code == 200
    data_gemini = resp_gemini.json()
    assert data_gemini["success"] is True
    assert data_gemini["active_provider"] == "gemini"
    # Debe tomar el modelo preestablecido en .env (ej. gemini-3.5-flash o gemini-2.5-flash)
    assert "gemini" in data_gemini["active_model"]

    # Regresar a ollama por defecto
    client.post("/api/v1/ai/models", json={"provider": "ollama"})


def test_update_ai_models_endpoint_invalid_provider():
    payload = {
        "provider": "non_existent_provider_xyz"
    }
    response = client.post("/api/v1/ai/models", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "no reconocido" in data["detail"]
