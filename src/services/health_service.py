from src import config
from src.services.ai import LLMService, is_ollama_available
from src.schemas import HealthResponse


def check_system_health() -> HealthResponse:
    """Verifica el estado del servicio, motor LLM (Ollama/OpenAI/Gemini/Claude) y archivos de persistencia."""
    llm_provider = config.LLM_PROVIDER
    llm_model = config.LLM_MODEL
    llm_available = False
    try:
        llm_svc = LLMService()
        llm_provider = llm_svc.provider_name
        llm_model = llm_svc.model_name
        llm_available = llm_svc.is_online
    except Exception:
        pass

    ollama_ok = False
    try:
        ollama_ok = is_ollama_available()
    except Exception:
        pass

    sheets_ok = bool(config.GOOGLE_SHEET_ID)
    sheet_url = f"https://docs.google.com/spreadsheets/d/{config.GOOGLE_SHEET_ID}/edit" if config.GOOGLE_SHEET_ID else None

    return HealthResponse(
        status="ok",
        llm_provider=llm_provider,
        llm_model=llm_model,
        llm_available=llm_available,
        ollama_available=ollama_ok,
        ollama_model=config.OLLAMA_MODEL,
        gmail_credentials_found=config.GMAIL_CREDENTIALS_PATH.exists(),
        gmail_token_found=bool(config.GMAIL_TOKEN_JSON or config.GMAIL_TOKEN_PATH.exists()),
        google_sheets_configured=sheets_ok,
        google_sheet_url=sheet_url,
        google_drive_folder_url=config.GOOGLE_DRIVE_FOLDER_URL if config.GOOGLE_DRIVE_FOLDER_URL else None,
        export_target=config.EXPORT_TARGET,
        server_excel_path=str(config.EXCEL_OUTPUT_PATH),
        server_json_path=str(config.OUTPUT_JSON_PATH),
    )
