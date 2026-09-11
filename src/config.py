"""
Configuración central del proyecto RAG for Mails.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Rutas base del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
DATA_DIR = BASE_DIR / "data"
SAMPLE_MAILS_DIR = DATA_DIR / "sample_mails"
OUTPUT_DIR = DATA_DIR / "output"
EXCEL_OUTPUT_PATH = OUTPUT_DIR / "reporte_moldeo.xlsx"
OUTPUT_JSON_PATH = OUTPUT_DIR / "output.json"
QUARANTINE_PATH = OUTPUT_DIR / "quarantine.json"
PROCESSED_EMAILS_PATH = OUTPUT_DIR / "processed_emails.json"

# Crear carpetas si no existen
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SAMPLE_MAILS_DIR.mkdir(parents=True, exist_ok=True)

# Configuración de Inteligencia Artificial (Multiproveedor)
raw_provider = os.getenv("LLM_PROVIDER", "ollama").strip().lower()
LLM_PROVIDER = "ollama" if raw_provider in ("none", "null", "") else raw_provider
LLM_MODEL = os.getenv("LLM_MODEL", "")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", os.getenv("OLLAMA_TEMPERATURE", "0.0")))

# Proveedor: Ollama (Local)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.0"))

# Proveedor: OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Proveedor: Google Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Proveedor: Anthropic Claude
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20240620")

# Configuración de Gmail API
GMAIL_CREDENTIALS_PATH = BASE_DIR / "credentials.json"
GMAIL_TOKEN_PATH = BASE_DIR / "token.json"
GMAIL_TOKEN_JSON = os.getenv("GMAIL_TOKEN_JSON", "").strip()
GMAIL_AUTHORIZED_SENDER = os.getenv("GMAIL_AUTHORIZED_SENDER", "l23200286@pachuca.tecnm.mx")
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify"
]

# Configuración del Servidor FastAPI
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
