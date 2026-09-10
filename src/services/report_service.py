from fastapi import HTTPException, status
from src.pipeline import IngestionPipeline
from src.schemas import ProcessTextRequest, ProcessTextResponse


def process_text_report(payload: ProcessTextRequest) -> ProcessTextResponse:
    """
    Coordina la extracción y validación de reportes de turno enviados directamente en texto,
    actualizando el Excel y JSON en el servidor.
    """
    if not payload.text or not payload.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El campo 'text' no puede estar vacío."
        )

    pipeline = IngestionPipeline(
        force_mock=payload.force_mock,
        provider=payload.llm_provider,
        model=payload.llm_model
    )
    result = pipeline.process_text(
        text=payload.text.strip(),
        source_file=payload.source_name or "api_direct"
    )

    records = result.report.records if result.success and result.report else []
    return ProcessTextResponse(
        success=result.success,
        records_extracted=len(records),
        records=records,
        server_excel_path=str(result.excel_path),
        server_json_path=str(result.json_path),
        error_message=result.error_message,
    )
