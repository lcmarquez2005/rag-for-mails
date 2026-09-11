from datetime import datetime, timezone
from typing import List, Optional, Union
import re
from pydantic import BaseModel, Field, field_validator


class MachineRecord(BaseModel):
    """
    Registro estructurado extraído con las llaves requeridas por la especificación:
    machine_id, downtime_minutes, approved_parts, rejected_parts, reasons, shift_leader.
    """
    machine_id: str = Field(
        ...,
        description="Identificador de máquina (ej: M102)"
    )
    downtime_minutes: int = Field(
        default=0,
        ge=0,
        description="Minutos totales de paro o inactividad"
    )
    approved_parts: int = Field(
        default=0,
        ge=0,
        description="Cantidad total de piezas conformes/aprobadas"
    )
    rejected_parts: int = Field(
        default=0,
        ge=0,
        description="Cantidad total de piezas rechazadas/defectuosas"
    )
    reasons: List[str] = Field(
        default_factory=list,
        description="Lista de motivos de paro, defectos o mantenimiento"
    )
    shift_leader: str = Field(
        ...,
        description="Nombre del líder o supervisor del turno"
    )
    shift: Optional[str] = Field(
        default="Turno No Especificado",
        description="Identificador del turno laboral (ej: 'Turno 1')"
    )

    @field_validator("machine_id")
    @classmethod
    def normalizar_machine_id(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            return ""
        v_clean = v.strip().upper()
        v_clean = re.sub(r'^(MAQUINA|MAQ|M)[-_\s]*', 'M', v_clean)
        if not re.match(r'^M\d{1,4}[A-Z]?$', v_clean):
            if re.match(r'^\d{1,4}$', v_clean):
                v_clean = f"M{v_clean}"
            else:
                return v_clean
        return v_clean

    @field_validator("shift_leader")
    @classmethod
    def normalizar_shift_leader(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            return ""
        return " ".join(v.strip().split()).title()

    @field_validator("shift")
    @classmethod
    def normalizar_shift(cls, v: Union[str, int, None]) -> str:
        if isinstance(v, int):
            return f"Turno {v}"
        if not v or not isinstance(v, str):
            return ""
        v_clean = v.strip()
        match = re.search(r'\b(1|2|3|uno|dos|tres)\b', v_clean, re.IGNORECASE)
        if match:
            num_map = {'1': '1', 'uno': '1', '2': '2', 'dos': '2', '3': '3', 'tres': '3'}
            turno_num = num_map.get(match.group(1).lower(), match.group(1))
            return f"Turno {turno_num}"
        return v_clean.title()

    @field_validator("reasons", mode="before")
    @classmethod
    def parse_reasons(cls, v) -> List[str]:
        if isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        if isinstance(v, str):
            if not v.strip():
                return []
            items = re.split(r'[,;\n]+', v)
            return [item.strip() for item in items if item.strip()]
        return []


class ExtractionOutput(BaseModel):
    records: List[MachineRecord] = Field(
        ...,
        description="Lista de registros de producción por máquina extraídos"
    )


class ShiftReport(BaseModel):
    records: List[MachineRecord]
    raw_source: str
    source_file: Optional[str] = None
    email_id: Optional[str] = None
    email_date: Optional[str] = None
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProcessedEmailLog(BaseModel):
    email_id: str
    email_date: Optional[str] = None
    sender: Optional[str] = None
    subject: Optional[str] = None
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    records_count: int = 0


class QuarantineRecord(BaseModel):
    raw_text: str
    source_file: Optional[str] = None
    error_message: str
    failed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


