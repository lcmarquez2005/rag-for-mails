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
