import json
from pathlib import Path
from typing import Optional, List, Any
from datetime import datetime, timezone

from src.config import QUARANTINE_PATH, SAMPLE_MAILS_DIR, OUTPUT_JSON_PATH, EXCEL_OUTPUT_PATH
from src.schemas import ShiftReport, QuarantineRecord
from src.extractor import get_extractor, BaseExtractor
from src.exporters import JsonExporter, ExcelExporter


class PipelineResult:
    """Resultado estructurado de la ejecución del pipeline."""
    def __init__(
        self,
        success: bool,
        report: Optional[ShiftReport] = None,
        json_path: Optional[Path] = None,
        excel_path: Optional[Path] = None,
        error_message: Optional[str] = None,
        source_file: Optional[str] = None
    ):
        self.success = success
        self.report = report
        self.json_path = json_path or OUTPUT_JSON_PATH
        self.excel_path = excel_path or EXCEL_OUTPUT_PATH
        self.error_message = error_message
        self.source_file = source_file


class IngestionPipeline:
    """
    Orquestador E2E:
    1. Ingesta (Archivo o Texto)
    2. Extracción Semántica (LangChain + Ollama / Mock)
    3. Validación de Esquema (Pydantic V2)
    4. Guardado en output.json y reporte_moldeo.xlsx
    """
    def __init__(
        self,
        extractor: Optional[BaseExtractor] = None,
        force_mock: bool = False,
        provider: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.extractor = extractor or get_extractor(
            force_mock=force_mock,
            provider=provider,
            model=model
        )
        self.json_exporter = JsonExporter()
        self.excel_exporter = ExcelExporter()

    def process_text(
        self,
        text: str,
        source_file: Optional[str] = None,
        email_id: Optional[str] = None,
        email_date: Optional[str] = None
    ) -> PipelineResult:
        """Procesa una cadena de texto sin estructurar."""
        if not text or not text.strip():
            return PipelineResult(
                success=False,
                error_message="El texto de entrada está vacío.",
                source_file=source_file
            )

        try:
            # 1. Extracción y Validación Pydantic
            report = self.extractor.extract(raw_text=text, source_file=source_file)
            report.email_id = email_id or (source_file if source_file and source_file.startswith("gmail_") else None)
            report.email_date = email_date

            # 2. Exportación a output.json (estructura original exacta)
            json_result = self.json_exporter.export_report(report)

            # 3. Exportación a Excel con deduplicación
            excel_file = self.excel_exporter.export_report(report)

            return PipelineResult(
                success=True,
                report=report,
                json_path=Path(json_result["output_file"]),
                excel_path=excel_file,
                source_file=source_file
            )

        except Exception as e:
            # Enrutamiento a Cuarentena para evitar caída del sistema
            self._send_to_quarantine(text, source_file, str(e))
            return PipelineResult(
                success=False,
                error_message=f"Error en extracción/validación: {str(e)}",
                source_file=source_file
            )

    def process_file(self, file_path: Path | str) -> PipelineResult:
        """Lee un archivo de correo/registro y ejecuta el pipeline."""
        p = Path(file_path)
        if not p.exists():
            return PipelineResult(
                success=False,
                error_message=f"El archivo {p} no existe.",
                source_file=str(p)
            )

        try:
            with open(p, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(p, "r", encoding="latin-1") as f:
                content = f.read()

        return self.process_text(text=content, source_file=p.name)

    def process_directory(self, dir_path: Path | str = SAMPLE_MAILS_DIR) -> List[PipelineResult]:
        """Procesa en lote todos los archivos de texto en un directorio."""
        p = Path(dir_path)
        if not p.exists():
            return []

        results = []
        for file in sorted(p.glob("*.txt")):
            res = self.process_file(file)
            results.append(res)
        return results

    def process_gmail_message(self, message: Any) -> PipelineResult:
        """
        Procesa un correo obtenido de Gmail (GmailMessage).
        Entrega el texto al pipeline de extracción y exportación con trazabilidad.
        """
        text = message.to_ingestion_text() if hasattr(message, "to_ingestion_text") else str(message)
        email_id = getattr(message, 'id', 'unknown')
        source_id = f"gmail_{email_id}"
        email_date = getattr(message, 'date', None)
        return self.process_text(
            text=text,
            source_file=source_id,
            email_id=email_id,
            email_date=email_date
        )


    def _send_to_quarantine(self, raw_text: str, source_file: Optional[str], error_message: str):
        """Registra entradas fallidas en el archivo de cuarentena."""
        quarantine_item = QuarantineRecord(
            raw_text=raw_text,
            source_file=source_file,
            error_message=error_message,
            failed_at=datetime.now(timezone.utc)
        )

        existing = []
        if QUARANTINE_PATH.exists():
            try:
                with open(QUARANTINE_PATH, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                existing = []

        existing.append(quarantine_item.model_dump(mode="json"))

        with open(QUARANTINE_PATH, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
