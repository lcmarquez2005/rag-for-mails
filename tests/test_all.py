import json
import pytest
from pathlib import Path
from src.schemas import MachineRecord, ExtractionOutput, ShiftReport
from src.extractor import sanitize_json_response, MockShiftExtractor
from src.exporters import JsonExporter, ExcelExporter
from src.pipeline import IngestionPipeline


def test_machine_record_validations():
    # Caso estándar con llaves principales
    record = MachineRecord(
        machine_id="m102 ",
        downtime_minutes=45,
        approved_parts=1200,
        rejected_parts=15,
        reasons="cambio de molde, defectos estéticos",
        shift_leader="juan pérez",
        shift="Turno 1"
    )

    # Validar normalización y datos extraídos
    assert record.machine_id == "M102"
    assert record.downtime_minutes == 45
    assert record.approved_parts == 1200
    assert record.rejected_parts == 15
    assert record.shift_leader == "Juan Pérez"
    assert record.shift == "Turno 1"
    assert record.reasons == ["cambio de molde", "defectos estéticos"]


def test_sanitize_json_response():
    # Respuesta con markdown envolvente
    markdown_wrapped = """
    Aquí está el resultado:
    ```json
    {
      "records": [
        {
          "machine_id": "M102",
          "downtime_minutes": 45,
          "approved_parts": 1200,
          "rejected_parts": 15,
          "reasons": ["cambio de molde"],
          "shift_leader": "Juan Pérez",
          "shift": "Turno 1"
        }
      ]
    }
    ```
    """
    data = sanitize_json_response(markdown_wrapped)
    assert "records" in data
    assert len(data["records"]) == 1
    assert data["records"][0]["machine_id"] == "M102"


def test_mock_extractor_standard_case():
    text = """Actualización del Turno 1: 
    La máquina M102 estuvo detenida durante 45 minutos debido a un cambio de molde. Total de piezas aprobadas: 1200. Piezas rechazadas: 15 debido a defectos estéticos. El equipo de mantenimiento completó las revisiones preventivas en la M102. 
    Líder de turno: Juan Pérez."""

    extractor = MockShiftExtractor()
    report = extractor.extract(text, source_file="test.txt")

    assert len(report.records) == 1
    rec = report.records[0]
    assert rec.machine_id == "M102"
    assert rec.downtime_minutes == 45
    assert rec.approved_parts == 1200
    assert rec.rejected_parts == 15
    assert rec.shift_leader == "Juan Pérez"


def test_pipeline_e2e_output_json_and_excel(tmp_path):
    json_file = tmp_path / "output.json"
    excel_file = tmp_path / "test_report.xlsx"

    pipeline = IngestionPipeline(force_mock=True)
    pipeline.json_exporter = JsonExporter(output_path=json_file)
    pipeline.excel_exporter = ExcelExporter(output_path=excel_file)

    sample_text = """Actualización del Turno 2:
    Máquina M105: 850 piezas aprobadas, 95 rechazadas por quemadura. Paro de 75 minutos.
    Líder de turno: Maria Rodriguez"""

    result = pipeline.process_text(sample_text, source_file="test_sample.txt")

    assert result.success is True
    assert json_file.exists()
    assert excel_file.exists()
    assert result.report.records[0].machine_id == "M105"

    # Verificar estructura original exacta en output.json
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, list)
    assert len(data) == 1
    record = data[0]
    assert record["machine_id"] == "M105"
    assert record["downtime_minutes"] == 75
    assert record["approved_parts"] == 850
    assert record["rejected_parts"] == 95
    assert record["shift_leader"] == "Maria Rodriguez"
    assert "reasons" in record
    # Sin adaptaciones ni campos ajenos
    assert "sheetId" not in record
    assert "cells" not in record
    assert "scrap_rate_pct" not in record

