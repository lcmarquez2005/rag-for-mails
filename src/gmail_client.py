import base64
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build

from src.config import (
    GMAIL_AUTHORIZED_SENDER,
    GMAIL_CREDENTIALS_PATH,
    GMAIL_SCOPES,
    GMAIL_TOKEN_PATH,
)


@dataclass
class GmailMessage:
    """Representación limpia de un correo recuperado de Gmail."""
    id: str
    thread_id: str
    sender: str
    recipient: str
    subject: str
    date: str
    snippet: str
    body: str

    def to_ingestion_text(self) -> str:
        """Devuelve el contenido listo para ser procesado por el pipeline."""
        return (
            f"Asunto: {self.subject}\n"
            f"De: {self.sender}\n"
            f"Fecha: {self.date}\n\n"
            f"{self.body}"
        ).strip()


def extract_email_address(from_header: str) -> str:
    """Extrae únicamente la dirección de correo de un encabezado 'From'."""
    match = re.search(r"<([^>]+)>", from_header)
    if match:
        return match.group(1).strip().lower()
    return from_header.strip().lower()


class GmailClient:
    """
    Cliente para la API oficial de Gmail.
    Cumple con el alcance de conexión, autenticación, filtrado por remitente
    y extracción de contenido.
    """

    def __init__(
        self,
        credentials_path: Path = GMAIL_CREDENTIALS_PATH,
        token_path: Path = GMAIL_TOKEN_PATH,
        authorized_sender: str = GMAIL_AUTHORIZED_SENDER,
        scopes: Optional[List[str]] = None,
        service: Optional[Resource] = None,
    ):
        self.credentials_path = Path(credentials_path)
        self.token_path = Path(token_path)
        self.authorized_sender = authorized_sender.lower().strip()
        self.scopes = scopes or GMAIL_SCOPES
        self._service: Optional[Resource] = service

    def authenticate(self, run_local_server: bool = True) -> Resource:
        """
        Autentica con la API de Gmail usando OAuth 2.0.
        Carga el token desde token.json si existe y es válido, o genera uno nuevo
        a partir de credentials.json abriendo el navegador.
        """
        if self._service:
            return self._service

        creds: Optional[Credentials] = None

        if self.token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_path), self.scopes)
            except Exception:
                creds = None

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not self.credentials_path.exists():
                    raise FileNotFoundError(
                        f"No se encontró el archivo de credenciales en {self.credentials_path}. "
                        "Descarga el archivo OAuth client credentials desde Google Cloud Console."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_path), self.scopes
                )
                creds = flow.run_local_server(port=0)

            with open(self.token_path, "w", encoding="utf-8") as token_file:
                token_file.write(creds.to_json())

        self._service = build("gmail", "v1", credentials=creds)
        return self._service

    @property
    def service(self) -> Resource:
        if self._service is None:
            return self.authenticate()
        return self._service

    def fetch_authorized_unread_emails(
        self,
        max_results: int = 10,
        sender_override: Optional[str] = None,
    ) -> List[GmailMessage]:
        """
        Consulta y recupera exclusivamente los correos no leídos que cumplan con
        el remitente autorizado.
        Filtro en Gmail: `is:unread from:<remitente_autorizado>`
        Validación estricta adicional en código para descartar cualquier otro remitente.
        """
        sender = (sender_override or self.authorized_sender).lower().strip()
        query = f"is:unread from:{sender}"

        service = self.service
        response = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )

        messages_meta = response.get("messages", [])
        if not messages_meta:
            return []

        authorized_emails: List[GmailMessage] = []

        for msg_meta in messages_meta:
            msg_id = msg_meta["id"]
            msg_data = (
                service.users()
                .messages()
                .get(userId="me", id=msg_id, format="full")
                .execute()
            )

            email_obj = self._parse_message(msg_data)
            if email_obj is None:
                continue

            # Doble validación estricta del remitente
            clean_sender = extract_email_address(email_obj.sender)
            if clean_sender == sender:
                authorized_emails.append(email_obj)

        return authorized_emails

    def mark_as_read(self, message_id: str) -> None:
        """Remueve la etiqueta UNREAD para evitar reprocesamiento."""
        service = self.service
        service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"removeLabelIds": ["UNREAD"]},
        ).execute()

    def _parse_message(self, msg_data: dict) -> Optional[GmailMessage]:
        """Extrae cabeceras y decodifica el cuerpo del mensaje."""
        msg_id = msg_data.get("id", "")
        thread_id = msg_data.get("threadId", "")
        snippet = msg_data.get("snippet", "")
        payload = msg_data.get("payload", {})
        headers = payload.get("headers", [])

        header_dict = {
            h.get("name", "").lower(): h.get("value", "") for h in headers
        }

        sender = header_dict.get("from", "")
        recipient = header_dict.get("to", "")
        subject = header_dict.get("subject", "(Sin Asunto)")
        date = header_dict.get("date", "")

        body_text = self._extract_body(payload)

        return GmailMessage(
            id=msg_id,
            thread_id=thread_id,
            sender=sender,
            recipient=recipient,
            subject=subject,
            date=date,
            snippet=snippet,
            body=body_text.strip(),
        )

    def _extract_body(self, payload: dict) -> str:
        """
        Navega de forma recursiva por los 'parts' MIME del correo y decodifica
        priorizando texto plano sobre HTML.
        """
        plain_text_parts: List[str] = []
        html_parts: List[str] = []

        def _traverse(part: dict):
            mime_type = part.get("mimeType", "")
            body = part.get("body", {})
            data = body.get("data")

            if data:
                try:
                    decoded = base64.urlsafe_b64decode(data.encode("ASCII")).decode(
                        "utf-8", errors="replace"
                    )
                    if mime_type == "text/plain":
                        plain_text_parts.append(decoded)
                    elif mime_type == "text/html":
                        html_parts.append(decoded)
                except Exception:
                    pass

            for subpart in part.get("parts", []):
                _traverse(subpart)

        _traverse(payload)

        if plain_text_parts:
            return "\n".join(plain_text_parts)

        if html_parts:
            html_content = "\n".join(html_parts)
            soup = BeautifulSoup(html_content, "html.parser")
            for tag in soup.find_all(["p", "div", "br", "tr", "li"]):
                tag.append("\n")
            lines = [line.strip() for line in soup.get_text().splitlines()]
            return "\n".join(line for line in lines if line)

        return ""
