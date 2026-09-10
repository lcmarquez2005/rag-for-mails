import pytest


@pytest.fixture(autouse=True)
def isolate_test_outputs(tmp_path, monkeypatch):
    """
    Aísla todas las escrituras de pruebas a un directorio temporal (tmp_path).
    Evita que la ejecución de tests contamine los archivos reales de producción en data/output/.
    """
    test_excel = tmp_path / "test_reporte_moldeo.xlsx"
    test_json = tmp_path / "test_output.json"
    test_tracker = tmp_path / "test_processed_emails.json"

    # Redirigir en src.config
    monkeypatch.setattr("src.config.EXCEL_OUTPUT_PATH", test_excel)
    monkeypatch.setattr("src.config.OUTPUT_JSON_PATH", test_json)
    monkeypatch.setattr("src.config.PROCESSED_EMAILS_PATH", test_tracker)

    # Redirigir en src.pipeline
    monkeypatch.setattr("src.pipeline.EXCEL_OUTPUT_PATH", test_excel)
    monkeypatch.setattr("src.pipeline.OUTPUT_JSON_PATH", test_json)
