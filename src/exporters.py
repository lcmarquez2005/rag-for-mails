import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from src.config import OUTPUT_JSON_PATH, EXCEL_OUTPUT_PATH
from src.schemas import ShiftReport


class ExcelExporter:
    """
    Gestiona la exportación de los datos limpios extraídos a un libro Excel (.xlsx).
    """
    def __init__(self, output_path: Path = EXCEL_OUTPUT_PATH):
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def export_report(self, report: ShiftReport) -> Path:
        wb, ws = self._get_or_create_workbook()

        font_regular = Font(name="Calibri", size=11)
        border_thin = Border(
            left=Side(style='thin', color='D9D9D9'),
            right=Side(style='thin', color='D9D9D9'),
            top=Side(style='thin', color='D9D9D9'),
            bottom=Side(style='thin', color='D9D9D9')
        )
        align_center = Alignment(horizontal="center", vertical="center")
        align_left = Alignment(horizontal="left", vertical="center")
        align_right = Alignment(horizontal="right", vertical="center")

        timestamp_str = report.processed_at.strftime("%Y-%m-%d %H:%M:%S")

        for record in report.records:
            row_data = [
                timestamp_str,
                record.shift or "N/A",
                record.machine_id,
                record.shift_leader,
                record.downtime_minutes,
                record.approved_parts,
                record.rejected_parts,
                ", ".join(record.reasons) if record.reasons else "N/A",
                report.source_file or "Entrada Directa"
            ]

            ws.append(row_data)
            row_idx = ws.max_row

            for col_idx in range(1, len(row_data) + 1):
                cell = ws.cell(row=row_idx, column=col_idx)
                cell.border = border_thin
                cell.font = font_regular
                if col_idx in (1, 2, 3):
                    cell.alignment = align_center
                elif col_idx in (5, 6, 7):
                    cell.alignment = align_right
                else:
                    cell.alignment = align_left

        self._auto_adjust_columns(ws)
        wb.save(self.output_path)
        return self.output_path

    def _get_or_create_workbook(self):
        headers = [
            "Fecha/Hora Proceso",
            "Turno",
            "Máquina ID",
            "Líder de Turno",
            "Paro (Minutos)",
            "Piezas Aprobadas",
            "Piezas Rechazadas",
            "Motivos / Observaciones",
            "Archivo Origen"
        ]

        if self.output_path.exists():
            wb = openpyxl.load_workbook(self.output_path)
            ws = wb.active
        else:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Reporte de Moldeo"

            ws.append(headers)
            header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
            header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

            ws.row_dimensions[1].height = 26
            for col_idx in range(1, len(headers) + 1):
                cell = ws.cell(row=1, column=col_idx)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_align

        return wb, ws

    def _auto_adjust_columns(self, ws):
        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)


class JsonExporter:
    """
    Exporta los registros procesados en formato JSON limpio con la estructura
    original exacta definida en la especificación del proyecto (output.json):
    - machine_id
    - downtime_minutes
    - approved_parts
    - rejected_parts
    - reasons
    - shift_leader
    """
    def __init__(self, output_path: Path = OUTPUT_JSON_PATH):
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def export_report(self, report: ShiftReport) -> Dict[str, Any]:
        """Guarda o anexa los registros con la estructura original limpia."""
        existing_data = []
        if self.output_path.exists():
            try:
                with open(self.output_path, "r", encoding="utf-8") as f:
                    content = json.load(f)
                    if isinstance(content, list):
                        existing_data = content
                    elif isinstance(content, dict):
                        existing_data = [content]
            except Exception:
                existing_data = []

        new_items = []
        for rec in report.records:
            item = {
                "machine_id": rec.machine_id,
                "downtime_minutes": rec.downtime_minutes,
                "approved_parts": rec.approved_parts,
                "rejected_parts": rec.rejected_parts,
                "reasons": rec.reasons,
                "shift_leader": rec.shift_leader
            }
            new_items.append(item)

        existing_data.extend(new_items)

        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, indent=2, ensure_ascii=False)

        return {
            "status": "success",
            "output_file": str(self.output_path),
            "records_inserted": len(new_items),
            "payload_sample": new_items
        }


# Alias para compatibilidad de importación
SmartsheetSimulator = JsonExporter
