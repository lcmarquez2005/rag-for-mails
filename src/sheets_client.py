"""
Cliente oficial para la API v4 de Google Sheets.
Permite autenticación unificada (OAuth2 / AWS Secrets Manager), inicialización
con formato corporativo idéntico a Excel, deduplicación e inserción atómica de filas.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build

from src import config

logger = logging.getLogger("rag_mails.sheets_client")

# Estilos corporativos idénticos al Excel existente
COLOR_HEADER_NAVY = {"red": 31 / 255.0, "green": 78 / 255.0, "blue": 121 / 255.0}  # #1F4E79
COLOR_WHITE = {"red": 1.0, "green": 1.0, "blue": 1.0}
COLOR_BG_WHITE = {"red": 1.0, "green": 1.0, "blue": 1.0}
COLOR_TEXT_BLACK = {"red": 0.0, "green": 0.0, "blue": 0.0}
COLOR_BORDER_GRAY = {"red": 217 / 255.0, "green": 217 / 255.0, "blue": 217 / 255.0}  # #D9D9D9

DEFAULT_HEADERS = [
    "ID de Correo / Origen",
    "Fecha del Correo",
    "Turno",
    "Máquina ID",
    "Líder de Turno",
    "Paro (Minutos)",
    "Piezas Aprobadas",
    "Piezas Rechazadas",
    "Motivos / Observaciones"
]


class GoogleSheetsClient:
    """
    Gestiona la conexión, autenticación, creación de estilos y anexado
    de filas a una hoja de cálculo única en Google Sheets.
    """

    def __init__(
        self,
        credentials_path: Path = config.GMAIL_CREDENTIALS_PATH,
        token_path: Path = config.GMAIL_TOKEN_PATH,
        scopes: Optional[List[str]] = None,
        service: Optional[Resource] = None,
    ):
        self.credentials_path = Path(credentials_path)
        self.token_path = Path(token_path)
        self.scopes = scopes or config.GOOGLE_SCOPES
        self._service: Optional[Resource] = service

    def authenticate(self, run_local_server: bool = True) -> Resource:
        """
        Autentica con Google Sheets API v4 usando OAuth 2.0.
        Prioriza la variable GMAIL_TOKEN_JSON en memoria (AWS Secrets Manager).
        Si no existe, lee token.json en disco.
        """
        if self._service is not None:
            return self._service

        creds: Optional[Credentials] = None

        # 1. Cargar desde variable de entorno (AWS Secrets Manager)
        if config.GMAIL_TOKEN_JSON:
            try:
                token_data = json.loads(config.GMAIL_TOKEN_JSON)
                creds = Credentials.from_authorized_user_info(token_data, self.scopes)
            except Exception as e:
                logger.warning(f"Error al deserializar GMAIL_TOKEN_JSON: {e}")
                creds = None

        # 2. Archivo físico token.json en disco
        if not creds and self.token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_path), self.scopes)
            except Exception as e:
                logger.warning(f"Error al leer token.json: {e}")
                creds = None

        # 3. Refrescar token si está expirado
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logger.error(f"Error refrescando token OAuth: {e}")
                    creds = None

            if not creds and run_local_server and self.credentials_path.exists():
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_path), self.scopes
                )
                creds = flow.run_local_server(port=0)
                try:
                    with open(self.token_path, "w", encoding="utf-8") as f:
                        f.write(creds.to_json())
                except Exception:
                    pass

            if not creds:
                raise FileNotFoundError(
                    "No se encontró un token válido para Google Sheets API. Asegúrate de configurar "
                    "GMAIL_TOKEN_JSON en AWS Secrets Manager o tener token.json con el scope "
                    "https://www.googleapis.com/auth/spreadsheets."
                )

        self._service = build("sheets", "v4", credentials=creds)
        return self._service

    @property
    def service(self) -> Resource:
        if self._service is None:
            return self.authenticate()
        return self._service

    def get_sheet_id_by_title(self, spreadsheet_id: str, tab_name: str) -> Optional[int]:
        """Obtiene el sheetId numérico de una pestaña por su título."""
        spreadsheet = self.service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        for sheet in spreadsheet.get("sheets", []):
            if sheet.get("properties", {}).get("title") == tab_name:
                return sheet.get("properties", {}).get("sheetId")
        return None

    def ensure_sheet_initialized(
        self,
        spreadsheet_id: str,
        tab_name: str = "Reportes",
        headers: Optional[List[str]] = None
    ) -> int:
        """
        Garantiza que la pestaña exista, tenga los encabezados correspondientes
        y aplique el formato idéntico al Excel:
          - Fila 1 inmovilizada (frozen row)
          - Encabezado Azul Marino (#1F4E79), texto blanco en negrita, centrado
          - Altura de fila 32px
        Devuelve el sheetId numérico de la pestaña.
        """
        headers = headers or DEFAULT_HEADERS
        service = self.service
        spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheets = spreadsheet.get("sheets", [])

        target_sheet_id: Optional[int] = None
        for sheet in sheets:
            props = sheet.get("properties", {})
            if props.get("title") == tab_name:
                target_sheet_id = props.get("sheetId")
                break

        # Si no existe la pestaña, crearla o renombrar la primera si está vacía
        if target_sheet_id is None:
            if len(sheets) == 1 and sheets[0].get("properties", {}).get("title") in ("Hoja 1", "Sheet1"):
                first_id = sheets[0].get("properties", {}).get("sheetId")
                service.spreadsheets().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body={
                        "requests": [{
                            "updateSheetProperties": {
                                "properties": {"sheetId": first_id, "title": tab_name},
                                "fields": "title"
                            }
                        }]
                    }
                ).execute()
                target_sheet_id = first_id
            else:
                resp = service.spreadsheets().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body={
                        "requests": [{
                            "addSheet": {
                                "properties": {"title": tab_name}
                            }
                        }]
                    }
                ).execute()
                target_sheet_id = resp["replies"][0]["addSheet"]["properties"]["sheetId"]

        # Verificar si la fila 1 ya tiene encabezados
        range_check = f"{tab_name}!A1:I1"
        res = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_check
        ).execute()
        existing_values = res.get("values", [])

        if not existing_values or len(existing_values[0]) == 0:
            # Insertar valores de encabezado
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range_check,
                valueInputOption="USER_ENTERED",
                body={"values": [headers]}
            ).execute()

            # Aplicar formato idéntico al Excel: Navy Blue, negrita, texto blanco, inmovilizar fila
            style_requests = [
                # 1. Inmovilizar fila 1
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": target_sheet_id,
                            "gridProperties": {"frozenRowCount": 1}
                        },
                        "fields": "gridProperties.frozenRowCount"
                    }
                },
                # 2. Altura de fila de encabezados (35 píxeles)
                {
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": target_sheet_id,
                            "dimension": "ROWS",
                            "startIndex": 0,
                            "endIndex": 1
                        },
                        "properties": {"pixelSize": 35},
                        "fields": "pixelSize"
                    }
                },
                # 3. Estilo visual de encabezados (Azul #1F4E79, blanco, bold, centrado)
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": target_sheet_id,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                            "startColumnIndex": 0,
                            "endColumnIndex": len(headers)
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": COLOR_HEADER_NAVY,
                                "horizontalAlignment": "CENTER",
                                "verticalAlignment": "MIDDLE",
                                "wrapStrategy": "WRAP",
                                "textFormat": {
                                    "foregroundColor": COLOR_WHITE,
                                    "fontSize": 11,
                                    "bold": True
                                }
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment,wrapStrategy)"
                    }
                }
            ]

            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": style_requests}
            ).execute()

        return target_sheet_id

    def get_existing_keys(self, spreadsheet_id: str, tab_name: str = "Reportes") -> Set[Tuple[str, str]]:
        """
        Lee las llaves compuestas (ID Correo, Máquina ID) ya registradas en la hoja
        para garantizar idempotencia total y evitar filas duplicadas.
        Columna A: ID Correo/Origen (índice 0)
        Columna D: Máquina ID (índice 3)
        """
        keys: Set[Tuple[str, str]] = set()
        try:
            res = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"{tab_name}!A:D"
            ).execute()
            rows = res.get("values", [])
            # Omitir fila 1 de encabezados
            for row in rows[1:]:
                if not row or len(row) < 1:
                    continue
                email_id = str(row[0]).strip()
                machine_id = str(row[3]).strip() if len(row) > 3 else ""
                if email_id and machine_id:
                    keys.add((email_id, machine_id))
        except Exception as e:
            logger.warning(f"No se pudieron leer llaves existentes de Google Sheets: {e}")
        return keys

    def append_rows(
        self,
        spreadsheet_id: str,
        rows: List[List[Any]],
        tab_name: str = "Reportes"
    ) -> int:
        """
        Inserta filas de forma atómica en Google Sheets y aplica el formato de celdas
        (bordes finos #D9D9D9 y alineación por tipo de columna).
        """
        if not rows:
            return 0

        target_sheet_id = self.ensure_sheet_initialized(spreadsheet_id, tab_name)

        # 1. Obtener última fila antes de insertar para conocer el rango exacto insertado
        res_meta = self.service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{tab_name}!A:A"
        ).execute()
        current_rows_count = len(res_meta.get("values", []))

        # 2. Inserción atómica de valores
        self.service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{tab_name}!A1",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": rows}
        ).execute()

        start_row = current_rows_count
        end_row = start_row + len(rows)

        # 3. Aplicar formato y bordes finos a las filas agregadas
        border_style = {
            "style": "SOLID",
            "width": 1,
            "color": COLOR_BORDER_GRAY
        }

        format_requests = [
            # 1. Formato tradicional de datos: Fondo blanco (#FFFFFF), texto negro regular, tamaño 10
            {
                "repeatCell": {
                    "range": {
                        "sheetId": target_sheet_id,
                        "startRowIndex": start_row,
                        "endRowIndex": end_row,
                        "startColumnIndex": 0,
                        "endColumnIndex": 9
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": COLOR_BG_WHITE,
                            "textFormat": {
                                "foregroundColor": COLOR_TEXT_BLACK,
                                "bold": False,
                                "fontSize": 10
                            },
                            "verticalAlignment": "MIDDLE"
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,verticalAlignment)"
                }
            },
            # 2. Bordes en todas las celdas insertadas
            {
                "updateBorders": {
                    "range": {
                        "sheetId": target_sheet_id,
                        "startRowIndex": start_row,
                        "endRowIndex": end_row,
                        "startColumnIndex": 0,
                        "endColumnIndex": 9
                    },
                    "top": border_style,
                    "bottom": border_style,
                    "left": border_style,
                    "right": border_style,
                    "innerHorizontal": border_style,
                    "innerVertical": border_style
                }
            },
            # 3. Columnas 0-3 (ID, Fecha, Turno, Máquina): Centro
            {
                "repeatCell": {
                    "range": {
                        "sheetId": target_sheet_id,
                        "startRowIndex": start_row,
                        "endRowIndex": end_row,
                        "startColumnIndex": 0,
                        "endColumnIndex": 4
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "horizontalAlignment": "CENTER",
                            "verticalAlignment": "MIDDLE"
                        }
                    },
                    "fields": "userEnteredFormat(horizontalAlignment,verticalAlignment)"
                }
            },
            # Columna 4 (Líder): Izquierda
            {
                "repeatCell": {
                    "range": {
                        "sheetId": target_sheet_id,
                        "startRowIndex": start_row,
                        "endRowIndex": end_row,
                        "startColumnIndex": 4,
                        "endColumnIndex": 5
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "horizontalAlignment": "LEFT",
                            "verticalAlignment": "MIDDLE"
                        }
                    },
                    "fields": "userEnteredFormat(horizontalAlignment,verticalAlignment)"
                }
            },
            # Columnas 5-7 (Paro, Aprobadas, Rechazadas): Derecha
            {
                "repeatCell": {
                    "range": {
                        "sheetId": target_sheet_id,
                        "startRowIndex": start_row,
                        "endRowIndex": end_row,
                        "startColumnIndex": 5,
                        "endColumnIndex": 8
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "horizontalAlignment": "RIGHT",
                            "verticalAlignment": "MIDDLE"
                        }
                    },
                    "fields": "userEnteredFormat(horizontalAlignment,verticalAlignment)"
                }
            },
            # Columna 8 (Motivos / Observaciones): Izquierda
            {
                "repeatCell": {
                    "range": {
                        "sheetId": target_sheet_id,
                        "startRowIndex": start_row,
                        "endRowIndex": end_row,
                        "startColumnIndex": 8,
                        "endColumnIndex": 9
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "horizontalAlignment": "LEFT",
                            "verticalAlignment": "MIDDLE"
                        }
                    },
                    "fields": "userEnteredFormat(horizontalAlignment,verticalAlignment)"
                }
            }
        ]

        try:
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": format_requests}
            ).execute()
        except Exception as e:
            logger.warning(f"No se pudieron aplicar estilos a las nuevas filas de Google Sheets: {e}")

        return len(rows)

    def format_all_data_rows(self, spreadsheet_id: str, tab_name: str = "Reportes") -> None:
        """Aplica el formato tradicional limpio (fondo blanco, texto negro, bordes finos) a todas las filas de datos."""
        target_sheet_id = self.get_sheet_id_by_title(spreadsheet_id, tab_name)
        if target_sheet_id is None:
            return

        res = self.service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{tab_name}!A:A"
        ).execute()
        total_rows = len(res.get("values", []))
        if total_rows <= 1:
            return

        border_style = {
            "style": "SOLID",
            "width": 1,
            "color": COLOR_BORDER_GRAY
        }

        requests = [
            # 1. Reset fondo blanco y texto negro
            {
                "repeatCell": {
                    "range": {
                        "sheetId": target_sheet_id,
                        "startRowIndex": 1,
                        "endRowIndex": total_rows,
                        "startColumnIndex": 0,
                        "endColumnIndex": 9
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": COLOR_BG_WHITE,
                            "textFormat": {
                                "foregroundColor": COLOR_TEXT_BLACK,
                                "bold": False,
                                "fontSize": 10
                            },
                            "verticalAlignment": "MIDDLE"
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,verticalAlignment)"
                }
            },
            # 2. Bordes finos en todas las celdas
            {
                "updateBorders": {
                    "range": {
                        "sheetId": target_sheet_id,
                        "startRowIndex": 1,
                        "endRowIndex": total_rows,
                        "startColumnIndex": 0,
                        "endColumnIndex": 9
                    },
                    "top": border_style,
                    "bottom": border_style,
                    "left": border_style,
                    "right": border_style,
                    "innerHorizontal": border_style,
                    "innerVertical": border_style
                }
            },
            # 3. Columnas 0-3 (ID, Fecha, Turno, Máquina): Centro
            {
                "repeatCell": {
                    "range": {
                        "sheetId": target_sheet_id,
                        "startRowIndex": 1,
                        "endRowIndex": total_rows,
                        "startColumnIndex": 0,
                        "endColumnIndex": 4
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "horizontalAlignment": "CENTER",
                            "verticalAlignment": "MIDDLE"
                        }
                    },
                    "fields": "userEnteredFormat(horizontalAlignment,verticalAlignment)"
                }
            },
            # 4. Columna 4 (Líder): Izquierda
            {
                "repeatCell": {
                    "range": {
                        "sheetId": target_sheet_id,
                        "startRowIndex": 1,
                        "endRowIndex": total_rows,
                        "startColumnIndex": 4,
                        "endColumnIndex": 5
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "horizontalAlignment": "LEFT",
                            "verticalAlignment": "MIDDLE"
                        }
                    },
                    "fields": "userEnteredFormat(horizontalAlignment,verticalAlignment)"
                }
            },
            # 5. Columnas 5-7 (Paro, Aprobadas, Rechazadas): Derecha
            {
                "repeatCell": {
                    "range": {
                        "sheetId": target_sheet_id,
                        "startRowIndex": 1,
                        "endRowIndex": total_rows,
                        "startColumnIndex": 5,
                        "endColumnIndex": 8
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "horizontalAlignment": "RIGHT",
                            "verticalAlignment": "MIDDLE"
                        }
                    },
                    "fields": "userEnteredFormat(horizontalAlignment,verticalAlignment)"
                }
            },
            # 6. Columna 8 (Motivos / Observaciones): Izquierda
            {
                "repeatCell": {
                    "range": {
                        "sheetId": target_sheet_id,
                        "startRowIndex": 1,
                        "endRowIndex": total_rows,
                        "startColumnIndex": 8,
                        "endColumnIndex": 9
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "horizontalAlignment": "LEFT",
                            "verticalAlignment": "MIDDLE"
                        }
                    },
                    "fields": "userEnteredFormat(horizontalAlignment,verticalAlignment)"
                }
            }
        ]

        self.service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests}
        ).execute()

