import os
from pathlib import Path

# Rutas base del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SAMPLE_MAILS_DIR = DATA_DIR / "sample_mails"
OUTPUT_DIR = DATA_DIR / "output"
EXCEL_OUTPUT_PATH = OUTPUT_DIR / "reporte_moldeo.xlsx"
OUTPUT_JSON_PATH = OUTPUT_DIR / "output.json"
JSON_OUTPUT_PATH = OUTPUT_JSON_PATH
QUARANTINE_PATH = OUTPUT_DIR / "quarantine.json"

# Crear carpetas si no existen
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SAMPLE_MAILS_DIR.mkdir(parents=True, exist_ok=True)

# Configuración de Ollama y Modelo LLM
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.0"))

# Configuración de Gmail API
GMAIL_CREDENTIALS_PATH = BASE_DIR / "credentials.json"
GMAIL_TOKEN_PATH = BASE_DIR / "token.json"
GMAIL_AUTHORIZED_SENDER = os.getenv("GMAIL_AUTHORIZED_SENDER", "l23200286@pachuca.tecnm.mx")
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify"
]
