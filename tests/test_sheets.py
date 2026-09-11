import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from src import config
from src.schemas import ShiftReport, MachineRecord
from src.sheets_client import GoogleSheetsClient, COLOR_HEADER_NAVY
from src.exporters import GoogleSheetsExporter
from src.pipeline import IngestionPipeline


@pytest.fixture
def sample_shift_report():
    return ShiftReport(
        raw_source="Texto original de prueba",
        email_id="gmail_test_123",
        email_date="2026-09-10 14:00:00",
        source_file="gmail_test_123",
        records=[
            MachineRecord(
                machine_id="M101",
                shift="Turno 1",
                shift_leader="Carlos Mendoza",
                downtime_minutes=35,
                approved_parts=1150,
                rejected_parts=12,
                reasons=["Ajuste mecánico"]
            ),
            MachineRecord(
                machine_id="M102",
                shift="Turno 1",
                shift_leader="Carlos Mendoza",
                downtime_minutes=0,
                approved_parts=1400,
                rejected_parts=5,
                reasons=[]
            )
        ]
    )


def test_sheets_client_ensure_initialized_new_sheet():
    mock_service = MagicMock()
    # Simular que existe la hoja default 'Sheet1'
    mock_service.spreadsheets().get().execute.return_value = {
        "sheets": [{"properties": {"sheetId": 0, "title": "Sheet1"}}]
    }
    # Simular que A1:I1 está vacío
    mock_service.spreadsheets().values().get().execute.return_value = {"values": []}

    client = GoogleSheetsClient(service=mock_service)
    sheet_id = client.ensure_sheet_initialized("sheet_fake_123", "Reportes")

    assert sheet_id == 0
    # Verificar que se actualizó el título y se insertaron encabezados
    mock_service.spreadsheets().batchUpdate.assert_called()
    mock_service.spreadsheets().values().update.assert_called_once()


def test_sheets_client_get_existing_keys():
    mock_service = MagicMock()
    mock_service.spreadsheets().values().get().execute.return_value = {
        "values": [
            ["ID de Correo / Origen", "Fecha", "Turno", "Máquina ID"],
            ["gmail_100", "2026-09-10", "Turno 1", "M101"],
            ["gmail_100", "2026-09-10", "Turno 1", "M102"],
        ]
    }
    client = GoogleSheetsClient(service=mock_service)
    keys = client.get_existing_keys("sheet_fake_123", "Reportes")

    assert ("gmail_100", "M101") in keys
    assert ("gmail_100", "M102") in keys
    assert ("gmail_200", "M101") not in keys


def test_sheets_client_append_rows():
    mock_service = MagicMock()
    mock_service.spreadsheets().get().execute.return_value = {
        "sheets": [{"properties": {"sheetId": 1234, "title": "Reportes"}}]
    }
    # Simular que ya tiene 1 fila (encabezado)
    mock_service.spreadsheets().values().get().execute.side_effect = [
        {"values": [["Header1"]]},  # check encabezado
        {"values": [["gmail_100"]]}, # check conteo de filas
    ]

    client = GoogleSheetsClient(service=mock_service)
    rows = [["gmail_101", "2026-09-10", "Turno 1", "M103", "Líder", 10, 100, 2, "N/A"]]
    inserted = client.append_rows("sheet_fake_123", rows, "Reportes")

    assert inserted == 1
    mock_service.spreadsheets().values().append.assert_called_once()
    mock_service.spreadsheets().batchUpdate.assert_called()


def test_sheets_exporter_disabled_when_no_id(sample_shift_report):
    exporter = GoogleSheetsExporter(sheet_id="")
    url = exporter.export_report(sample_shift_report)
    assert url is None


def test_sheets_exporter_success_and_deduplication(sample_shift_report):
    mock_client = MagicMock()
    # Simular que M101 ya existe pero M102 no
    mock_client.get_existing_keys.return_value = {
        ("gmail_test_123", "M101")
    }

    exporter = GoogleSheetsExporter(
        sheet_id="fake_spreadsheet_id",
        tab_name="Reportes",
        client=mock_client
    )

    url = exporter.export_report(sample_shift_report)

    assert url == "https://docs.google.com/spreadsheets/d/fake_spreadsheet_id/edit"
    mock_client.append_rows.assert_called_once()
    # Solo debe insertarse M102 porque M101 ya existía
    args, kwargs = mock_client.append_rows.call_args
    rows_inserted = args[1]
    assert len(rows_inserted) == 1
    assert rows_inserted[0][3] == "M102"


def test_sheets_exporter_resilience_on_exception(sample_shift_report):
    mock_client = MagicMock()
    mock_client.get_existing_keys.side_effect = RuntimeError("Google API Rate Limit Exceeded")

    exporter = GoogleSheetsExporter(
        sheet_id="fake_spreadsheet_id",
        client=mock_client
    )

    # No debe crashear la ejecución, debe capturar la excepción y devolver None
    url = exporter.export_report(sample_shift_report)
    assert url is None


def test_pipeline_with_sheets_export(monkeypatch, sample_shift_report):
    mock_sheets_exporter = MagicMock()
    mock_sheets_exporter.export_report.return_value = "https://docs.google.com/spreadsheets/d/sheet_test/edit"

    monkeypatch.setattr(config, "EXPORT_TARGET", "both")

    pipeline = IngestionPipeline(force_mock=True)
    pipeline.sheets_exporter = mock_sheets_exporter

    text = "Turno 1: Máquina M101 detenida 35 min. 1150 piezas aprobadas, 12 rechazadas. Líder: Carlos Mendoza"
    result = pipeline.process_text(text, source_file="gmail_test_123", email_id="gmail_test_123")

    assert result.success is True
    assert result.sheet_url == "https://docs.google.com/spreadsheets/d/sheet_test/edit"
    assert result.excel_path is not None
    mock_sheets_exporter.export_report.assert_called_once()
