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


SPANISH_WORD_NUMBERS = {
    "cero": 0, "ningun": 0, "ninguna": 0, "ninguno": 0, "sin": 0,
    "un": 1, "uno": 1, "una": 1,
    "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9,
    "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
    "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19,
    "veinte": 20, "veinticinco": 25, "treinta": 30, "treinta y cinco": 35,
    "cuarenta": 40, "cuarenta y cinco": 45, "cincuenta": 50, "sesenta": 60,
    "setenta": 70, "setenta y cinco": 75, "ochenta": 80, "noventa": 90,
    "cien": 100, "ciento": 100, "doscientos": 200, "doscientas": 200,
    "trescientos": 300, "trescientas": 300, "cuatrocientos": 400, "cuatrocientas": 400,
    "quinientos": 500, "quinientas": 500, "seiscientos": 600, "seiscientas": 600,
    "setecientos": 700, "setecientas": 700, "ochocientos": 800, "ochocientas": 800,
    "ochocientos cincuenta": 850, "ochocientas cincuenta": 850,
    "novecientos": 900, "novecientas": 900,
    "mil": 1000, "mil doscientos": 1200, "mil doscientas": 1200,
    "mil quinientos": 1500, "mil quinientas": 1500,
}


def extract_number_from_text(segment: str, default: int = 0) -> int:
    """Extrae un valor numérico ya sea expresado en dígitos o en palabras en español."""
    seg = segment.strip().lower()
    digit_match = re.search(r'\b(\d+)\b', seg)
    if digit_match:
        return int(digit_match.group(1))

    for phrase in sorted(SPANISH_WORD_NUMBERS.keys(), key=len, reverse=True):
        if re.search(rf'\b{re.escape(phrase)}\b', seg):
            return SPANISH_WORD_NUMBERS[phrase]

    return default


class MockShiftExtractor(BaseExtractor):
    """
    Extractor determinista basado en reglas y regex.
    Permite razonamiento semántico para números en texto, normalización de turnos
    y tolerancia ortográfica básica.
    """
    def extract(self, raw_text: str, source_file: Optional[str] = None) -> ShiftReport:
        # Detección de supervisor
        leader_match = re.search(
            r'(?:Líder de turno|Supervisor a cargo|Supervisor|superbisor|Líder|lider):\s*([^\n\r.]+)',
            raw_text,
            re.IGNORECASE
        )
        shift_leader = leader_match.group(1).strip() if leader_match else "Supervisor Moldeo"

        # Detección y normalización estricta del turno (Turno 1, Turno 2, Turno 3)
        shift = "Turno 1"
        shift_match = re.search(
            r'(?:turno\s*([123]|uno|dos|tres|1er|2do|3er)|(primer|segundo|tercer)\s*turno|t\s*([123]))',
            raw_text,
            re.IGNORECASE
        )
        if shift_match:
            matched = shift_match.group(0).lower()
            if any(k in matched for k in ("2", "dos", "segundo", "2do", "vespertino")):
                shift = "Turno 2"
            elif any(k in matched for k in ("3", "tres", "tercer", "3er", "nocturno")):
                shift = "Turno 3"
            else:
                shift = "Turno 1"

        # Identificar todas las máquinas únicas mencionadas
        all_machines = re.findall(r'\bM\d{2,4}\b', raw_text, flags=re.IGNORECASE)
        if not all_machines:
            loose_machines = re.findall(r'(?:máquina|maquina|maquna|maq|inyectora)\s*[:=]?\s*(\d{2,4})', raw_text, flags=re.IGNORECASE)
            all_machines = [f"M{m}" for m in loose_machines]

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
                    if re.search(rf'\b{um}\b', line, re.IGNORECASE) and any(kw in line.lower() for kw in ['máquina', 'maquina', 'maquna', ':']):
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
        # Minutos de paro (dígitos, palabras o expresiones de tiempo)
        b_lower = block.lower()
        if "sin paro" in b_lower or "cero paro" in b_lower or "continuo sin paros" in b_lower:
            downtime = 0
        elif "hora y media" in b_lower or "1.5 horas" in b_lower or "1.5 hrs" in b_lower:
            downtime = 90
        elif "media hora" in b_lower:
            downtime = 30
        elif "una hora" in b_lower:
            downtime = 60
        elif "dos horas" in b_lower:
            downtime = 120
        else:
            down_match = re.search(r'(?:detenida durante|paro de|parada|paroo|fuera de servicio|tiempo detenido)?\s*:?\s*(\d+|[a-záéíóúñ\s]+?)\s*(?:minutos|min|m\b)', block, re.IGNORECASE)
            if down_match:
                downtime = extract_number_from_text(down_match.group(1), default=0)
            else:
                down_hour_match = re.search(r'(\d+)\s*(?:horas?|hrs?|h\b)', block, re.IGNORECASE)
                downtime = int(down_hour_match.group(1)) * 60 if down_hour_match else 0

        # Piezas aprobadas (aprobadas, aprovadas, buenas, conformes, etc.)
        appr_before = re.search(r'(\d+|[a-záéíóúñ]+(?:\s+[a-záéíóúñ]+){0,3})\s*(?:piezas?\s+)?(?:aprobadas?|aprovadas?|buenas?|conformes?)', block, re.IGNORECASE)
        approved = 0
        if appr_before:
            appr_raw = re.sub(r'^(?:se\s+sacaron|se\s+fabricaron|total\s+de|hubo|salieron|y|,)\s+', '', appr_before.group(1), flags=re.IGNORECASE)
            approved = extract_number_from_text(appr_raw, default=0)

        if approved == 0:
            appr_after = re.search(r'(?:piezas?\s+)?(?:aprobadas?|aprovadas?|buenas?|conformes?)\s*[:=]?\s*(\d+|[a-záéíóúñ]+(?:\s+[a-záéíóúñ]+){0,3})', block, re.IGNORECASE)
            if appr_after:
                approved = extract_number_from_text(appr_after.group(1), default=0)

        # Piezas rechazadas (rechazadas, rechasadas, defectuosas, scrap, defestos)
        rej_before = re.search(r'(\d+|[a-záéíóúñ]+(?:\s+[a-záéíóúñ]+){0,2})\s*(?:piezas?\s+)?(?:rechazadas?|rechasadas?|defectuosas?|scrap|defestos?)', block, re.IGNORECASE)
        rejected = 0
        if rej_before:
            rej_raw = re.sub(r'^(?:y|,|con)\s+', '', rej_before.group(1), flags=re.IGNORECASE)
            rejected = extract_number_from_text(rej_raw, default=0)

        if rejected == 0:
            rej_after = re.search(r'(?:piezas?\s+)?(?:rechazadas?|rechasadas?|defectuosas?|scrap|defestos?)\s*[:=]?\s*(\d+|[a-záéíóúñ]+(?:\s+[a-záéíóúñ]+){0,2})(?:\s+por|\s+debido|[.,;\n]|$)', block, re.IGNORECASE)
            if rej_after:
                rejected = extract_number_from_text(rej_after.group(1), default=0)

        b = block.lower()
        # Justificaciones y causas reales
        extracted_reasons = []
        for match in re.finditer(r'(?:por|debido a|motivo:?|causa:?)\s+([^\n\r.,;]+)', block, re.IGNORECASE):
            cause = match.group(1).strip()
            if cause and not re.match(r'^(?:\d+|el|la|los|las|supervisor)\b', cause, re.IGNORECASE):
                extracted_reasons.append(cause)

        rule_reasons = [label for kws, label in REASON_RULES if any(kw in b for kw in kws)]
        reasons = extracted_reasons or rule_reasons or (["operación continua"] if downtime == 0 and rejected == 0 else ["operación regular"])

        leader_match = re.search(r'(?:l[íi]der(?:\s+de\s+turno)?|super[bv]i?sor(?:\s+a\s+cargo)?)\s*[:=]?\s*([^\r\n,;.]+)', block, re.IGNORECASE)
        leader = leader_match.group(1).strip().title() if leader_match else default_leader

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
