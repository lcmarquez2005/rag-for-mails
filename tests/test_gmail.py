import base64
from unittest.mock import MagicMock

from src.gmail_client import GmailClient, GmailMessage, extract_email_address
from src.pipeline import IngestionPipeline


def test_extract_email_address():
    assert extract_email_address("Lider <l23200286@pachuca.tecnm.mx>") == "l23200286@pachuca.tecnm.mx"
    assert extract_email_address("  l23200286@pachuca.tecnm.mx  ") == "l23200286@pachuca.tecnm.mx"


def test_gmail_message_to_ingestion_text():
    msg = GmailMessage(
        id="12345",
        thread_id="th1",
        sender="l23200286@pachuca.tecnm.mx",
        recipient="me@domain.com",
        subject="Reporte Turno 1",
        date="Wed, 10 Sep 2026 08:00:00 -0600",
        snippet="Turno 1...",
        body="Máquina M102 estuvo detenida 45 min..."
    )
    text = msg.to_ingestion_text()
    assert "Asunto: Reporte Turno 1" in text
    assert "De: l23200286@pachuca.tecnm.mx" in text
    assert "Máquina M102" in text


def test_parse_message_plain_text():
    client = GmailClient(authorized_sender="l23200286@pachuca.tecnm.mx")
    raw_text = "Reporte de turno estándar\nMáquina M102"
    encoded_data = base64.urlsafe_b64encode(raw_text.encode("utf-8")).decode("ascii")

    msg_data = {
        "id": "msg_001",
        "threadId": "th_001",
        "snippet": "Reporte de turno estándar...",
        "payload": {
            "headers": [
                {"name": "From", "value": "Turno Lider <l23200286@pachuca.tecnm.mx>"},
                {"name": "To", "value": "planta@empresa.com"},
                {"name": "Subject", "value": "Reporte Moldeo M102"},
                {"name": "Date", "value": "Wed, 10 Sep 2026 08:00:00 -0600"}
            ],
            "mimeType": "text/plain",
            "body": {
                "data": encoded_data
            }
        }
    }

    parsed = client._parse_message(msg_data)
    assert parsed is not None
    assert parsed.id == "msg_001"
    assert parsed.subject == "Reporte Moldeo M102"
    assert parsed.sender == "Turno Lider <l23200286@pachuca.tecnm.mx>"
    assert "Reporte de turno estándar" in parsed.body


def test_parse_message_multipart_html_fallback():
    client = GmailClient(authorized_sender="l23200286@pachuca.tecnm.mx")
    raw_html = "<p>Actualización <b>Turno 2</b></p><div>Máquina M105</div>"
    encoded_data = base64.urlsafe_b64encode(raw_html.encode("utf-8")).decode("ascii")

    msg_data = {
        "id": "msg_002",
        "threadId": "th_002",
        "snippet": "Actualización...",
        "payload": {
            "headers": [
                {"name": "From", "value": "l23200286@pachuca.tecnm.mx"},
                {"name": "Subject", "value": "Reporte HTML"}
            ],
            "mimeType": "multipart/alternative",
            "parts": [
                {
                    "mimeType": "text/html",
                    "body": {"data": encoded_data}
                }
            ]
        }
    }

    parsed = client._parse_message(msg_data)
    assert parsed is not None
    assert "Actualización Turno 2" in parsed.body
    assert "Máquina M105" in parsed.body


def test_fetch_authorized_unread_emails_filters_unauthorized():
    mock_service = MagicMock()
    client = GmailClient(
        authorized_sender="l23200286@pachuca.tecnm.mx",
        service=mock_service
    )

    # Simular lista de mensajes devueltos por Gmail
    mock_service.users().messages().list().execute.return_value = {
        "messages": [{"id": "auth_1"}, {"id": "spam_2"}]
    }

    # Simular mensaje 1 (autorizado)
    enc_auth = base64.urlsafe_b64encode(b"Contenido autorizado").decode("ascii")
    data_auth = {
        "id": "auth_1",
        "threadId": "th1",
        "snippet": "Autorizado",
        "payload": {
            "headers": [
                {"name": "From", "value": "Ingeniero <l23200286@pachuca.tecnm.mx>"},
                {"name": "Subject", "value": "Reporte Real"}
            ],
            "body": {"data": enc_auth}
        }
    }

    # Simular mensaje 2 (no autorizado / spam)
    enc_spam = base64.urlsafe_b64encode(b"Spam").decode("ascii")
    data_spam = {
        "id": "spam_2",
        "threadId": "th2",
        "snippet": "Spam",
        "payload": {
            "headers": [
                {"name": "From", "value": "Spammer <spammer@externo.com>"},
                {"name": "Subject", "value": "Oferta"}
            ],
            "body": {"data": enc_spam}
        }
    }

    def mock_get(userId, id, format):
        mock_call = MagicMock()
        if id == "auth_1":
            mock_call.execute.return_value = data_auth
        else:
            mock_call.execute.return_value = data_spam
        return mock_call

    mock_service.users().messages().get.side_effect = mock_get

    emails = client.fetch_authorized_unread_emails()

    # Debe contener únicamente el mensaje del remitente autorizado
    assert len(emails) == 1
    assert emails[0].id == "auth_1"
    assert emails[0].sender == "Ingeniero <l23200286@pachuca.tecnm.mx>"


def test_fetch_authorized_unread_emails_accepts_multiple_senders():
    mock_service = MagicMock()
    client = GmailClient(
        authorized_sender="lider@empresa.com, supervisor@empresa.com",
        service=mock_service,
    )

    mock_service.users().messages().list().execute.return_value = {
        "messages": [{"id": "leader_1"}, {"id": "supervisor_2"}, {"id": "other_3"}]
    }

    def message_data(message_id, sender):
        return {
            "id": message_id,
            "threadId": f"thread_{message_id}",
            "payload": {
                "headers": [{"name": "From", "value": sender}],
                "body": {"data": base64.urlsafe_b64encode(b"Reporte").decode("ascii")},
            },
        }

    messages = {
        "leader_1": message_data("leader_1", "Lider <lider@empresa.com>"),
        "supervisor_2": message_data("supervisor_2", "supervisor@empresa.com"),
        "other_3": message_data("other_3", "externo@empresa.com"),
    }

    def mock_get(userId, id, format):
        mock_call = MagicMock()
        mock_call.execute.return_value = messages[id]
        return mock_call

    mock_service.users().messages().get.side_effect = mock_get

    emails = client.fetch_authorized_unread_emails()

    assert {email.id for email in emails} == {"leader_1", "supervisor_2"}
    query = mock_service.users().messages().list.call_args.kwargs["q"]
    assert query == "is:unread {from:lider@empresa.com from:supervisor@empresa.com}"


def test_mark_as_read():
    mock_service = MagicMock()
    client = GmailClient(service=mock_service)
    client.mark_as_read("msg_123")

    mock_service.users().messages().modify.assert_called_once_with(
        userId="me",
        id="msg_123",
        body={"removeLabelIds": ["UNREAD"]}
    )


def test_pipeline_process_gmail_message(tmp_path):
    pipeline = IngestionPipeline(force_mock=True)
    msg = GmailMessage(
        id="gmail_999",
        thread_id="th_999",
        sender="l23200286@pachuca.tecnm.mx",
        recipient="planta@moldeo.com",
        subject="Reporte M102 Turno 1",
        date="2026-09-10",
        snippet="M102",
        body="La máquina M102 estuvo detenida durante 45 minutos debido a un cambio de molde. Total de piezas aprobadas: 1200. Piezas rechazadas: 15 debido a defectos estéticos. Líder de turno: Juan Pérez."
    )

    result = pipeline.process_gmail_message(msg)
    assert result.success is True
    assert result.report is not None
    assert len(result.report.records) == 1
    rec = result.report.records[0]
    assert rec.machine_id == "M102"
    assert rec.approved_parts == 1200
    assert rec.shift_leader == "Juan Pérez"


