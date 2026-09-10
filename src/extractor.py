from typing import Optional
import re

from src.schemas import MachineRecord, ExtractionOutput, ShiftReport
from src.services.ai import (
    LLMService,
    OllamaService,
    is_ollama_available,
    sanitize_json_response,
)

REASON_RULES = (
    (("cambio de molde",), "cambio de molde"),
    (("defectos estéticos",), "defectos estéticos"),
    (("preventiva", "mantenimiento", "husillo"), "mantenimiento y revisiones"),
    (("rebaba",), "rebabas en pieza"),
    (("sensor", "presión"), "falla sensor"),
    (("temperatura", "termopar", "quemadura"), "ajuste térmico / quemadura"),
    (("purga",), "purga de boquilla"),
)


class BaseExtractor:
    """Interfaz base para extractores de información de turnos."""
    def extract(self, raw_text: str, source_file: Optional[str] = None) -> ShiftReport:
        raise NotImplementedError


class LLMShiftExtractor(BaseExtractor):
    """
    Extractor de información que delega la inferencia y conexión
    con el proveedor de IA configurado (Ollama, OpenAI, Gemini o Claude).
    """
    def __init__(
        self,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None,
        api_key: Optional[str] = None
    ):
        self.service = LLMService(
            provider=provider,
            model_name=model_name,
            base_url=base_url,
            temperature=temperature,
            api_key=api_key
        )

    def extract(self, raw_text: str, source_file: Optional[str] = None) -> ShiftReport:
        data = self.service.invoke_extraction(raw_text)
        validated_output = ExtractionOutput(**data)

        return ShiftReport(
            records=validated_output.records,
            raw_source=raw_text,
            source_file=source_file
        )


# Alias de compatibilidad
OllamaShiftExtractor = LLMShiftExtractor


class MockShiftExtractor(BaseExtractor):
    """
    Extractor determinista basado en reglas y regex.
    Permite ejecutar la solución y todas las pruebas de forma instantánea sin requerir GPU ni Ollama.
    """
    def extract(self, raw_text: str, source_file: Optional[str] = None) -> ShiftReport:
        # Detección de supervisor
        leader_match = re.search(r'(?:Líder de turno|Supervisor a cargo|Supervisor|Líder):\s*([^\n\r.]+)', raw_text, re.IGNORECASE)
        shift_leader = leader_match.group(1).strip() if leader_match else "Supervisor Moldeo"

        # Detección de turno
        shift_match = re.search(r'(Turno\s*[123]|Turno\s*(?:uno|dos|tres))', raw_text, re.IGNORECASE)
        shift = shift_match.group(1).strip() if shift_match else "Turno 1"

        # Identificar todas las máquinas únicas mencionadas
        all_machines = re.findall(r'\bM\d{2,4}\b', raw_text, flags=re.IGNORECASE)
        unique_machines = list(dict.fromkeys([m.upper() for m in all_machines]))
        if not unique_machines:
            unique_machines = ["M102"]

        records = []
        if len(unique_machines) == 1:
            m_id = unique_machines[0]
            records.append(self._parse_machine_block(raw_text, m_id, shift, shift_leader))
        else:
            lines = raw_text.splitlines()
            current_m = None
            current_lines = []

            for line in lines:
                m_found = None
                for um in unique_machines:
                    if re.search(rf'\b{um}\b', line, re.IGNORECASE) and any(kw in line.lower() for kw in ['máquina', 'maquina', ':']):
                        m_found = um
                        break

                if m_found:
                    if current_m and current_lines:
                        records.append(self._parse_machine_block("\n".join(current_lines), current_m, shift, shift_leader))
                    current_m = m_found
                    current_lines = [line]
                else:
                    current_lines.append(line)

            if current_m and current_lines:
                records.append(self._parse_machine_block("\n".join(current_lines), current_m, shift, shift_leader))

        return ShiftReport(
            records=records,
            raw_source=raw_text,
            source_file=source_file
        )

    def _parse_machine_block(self, block: str, machine_id: str, shift: str, default_leader: str) -> MachineRecord:
        down_match = re.search(r'(?:detenida durante|paro de|parada|fuera de servicio|tiempo detenido)?\s*:?\s*(\d+)\s*(?:minutos|min|m\b)', block, re.IGNORECASE)
        if not down_match:
            down_hour_match = re.search(r'(\d+)\s*(?:horas?|hrs?|h\b)', block, re.IGNORECASE)
            downtime = int(down_hour_match.group(1)) * 60 if down_hour_match else 0
        else:
            downtime = int(down_match.group(1))

        appr_match = re.search(r'(?:piezas\s+(?:aprobadas|buenas|conformes)(?:\s+producidas)?|conformes|aprobadas)\s*[:=]?\s*(\d+)', block, re.IGNORECASE)
        if not appr_match:
            appr_match = re.search(r'(\d+)\s*(?:piezas\s+)?(?:aprobadas|buenas|conformes)', block, re.IGNORECASE)
        approved = int(appr_match.group(1)) if appr_match else 0

        rej_match = re.search(r'(?:piezas\s+(?:rechazadas|defectuosas)|scrap|no\s+conformes|rechazadas)\s*(?:[/:=-]|\w+)*\s*[:=]?\s*(\d+)', block, re.IGNORECASE)
        if not rej_match:
            rej_match = re.search(r'(\d+)\s*(?:piezas\s+)?(?:rechazadas|defectuosas|scrap|no\s+conformes)', block, re.IGNORECASE)
        rejected = int(rej_match.group(1)) if rej_match else 0

        b = block.lower()
        reasons = [label for kws, label in REASON_RULES if any(kw in b for kw in kws)] or ["operación regular"]

        leader_match = re.search(r'(?:Líder de turno|Supervisor a cargo|Supervisor|Líder):\s*([^\n\r.]+)', block, re.IGNORECASE)
        leader = leader_match.group(1).strip() if leader_match else default_leader

        return MachineRecord(
            machine_id=machine_id,
            downtime_minutes=downtime,
            approved_parts=approved,
            rejected_parts=rejected,
            reasons=reasons,
            shift_leader=leader,
            shift=shift
        )


def get_extractor(
    force_mock: bool = False,
    provider: Optional[str] = None,
    model: Optional[str] = None
) -> BaseExtractor:
    """
    Fábrica inteligente de extractores:
    Si no se fuerza mock y el servicio LLM configurado está disponible
    (Ollama, OpenAI, Gemini o Claude), utiliza LLMShiftExtractor;
    en caso contrario, utiliza MockShiftExtractor.
    """
    if force_mock:
        return MockShiftExtractor()

    service = LLMService(provider=provider, model_name=model)
    if service.is_online:
        return LLMShiftExtractor(provider=provider, model_name=model)
    return MockShiftExtractor()
