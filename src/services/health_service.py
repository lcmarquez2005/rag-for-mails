from src import config
from src.services.ollama_service import is_ollama_available
from src.schemas import HealthResponse


def check_system_health() -> HealthResponse:
    """Verifica el estado del servicio, motor LLM (Ollama) y archivos de persistencia."""
    return HealthResponse(
        status="ok",
        ollama_available=is_ollama_available(),
        ollama_model=config.OLLAMA_MODEL,
        gmail_credentials_found=config.GMAIL_CREDENTIALS_PATH.exists(),
        gmail_token_found=config.GMAIL_TOKEN_PATH.exists(),
        server_excel_path=str(config.EXCEL_OUTPUT_PATH),
        server_json_path=str(config.OUTPUT_JSON_PATH),
    )
