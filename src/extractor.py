import json
import re
import urllib.request
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_ollama import OllamaLLM

from src.config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TEMPERATURE
from src.schemas import MachineRecord, ExtractionOutput, ShiftReport


EXTRACTION_SYSTEM_PROMPT = """Eres un sistema experto en extracción y normalización de datos para plantas de manufactura y moldeo por inyección.
Tu objetivo es analizar registros de turno no estructurados (enviados por correo o chat) y extraer exactamente los datos de producción en formato JSON estructurado.

REGLAS ESTRICTAS DE EXTRACCIÓN:
1. Extrae cada máquina mencionada en una lista bajo la clave "records".
2. Cada elemento de "records" DEBE contener exactamente las siguientes llaves:
   - "machine_id": Identificador alfanumérico de la máquina (ej: "M102", "M105"). Si el texto dice "máquina 102", normalízalo a "M102".
   - "downtime_minutes": Número entero con los minutos de inactividad o paro. Si no hubo paro o estuvo al 100%, usa 0. Convierte horas a minutos (ej: 1 hora = 60).
   - "approved_parts": Número entero de piezas aprobadas / buenas / conformes producidas. Si no se especifica, usa 0.
   - "rejected_parts": Número entero de piezas rechazadas / defectuosas / scrap. Si no se especifica, usa 0.
   - "reasons": Lista de strings con todos los motivos de paro, fallas, defectos estéticos o notas de mantenimiento.
   - "shift_leader": Nombre del supervisor o líder de turno indicado en el reporte.
   - "shift": Identificador del turno si se menciona (ej: "Turno 1", "Turno 2", "Turno 3").

3. FORMATO DE SALIDA:
Debes responder ÚNICAMENTE con el objeto JSON válido. NO incluyas explicaciones, ni saludos, ni texto antes o después del JSON.

EJEMPLO DE SALIDA:
{
  "records": [
    {
      "machine_id": "M102",
      "downtime_minutes": 45,
      "approved_parts": 1200,
      "rejected_parts": 15,
      "reasons": ["cambio de molde", "defectos estéticos", "revisiones preventivas completadas"],
      "shift_leader": "Juan Pérez",
      "shift": "Turno 1"
    }
  ]
}
"""

FEW_SHOT_USER_EXAMPLE = """Actualización del Turno 1: 
La máquina M102 estuvo detenida durante 45 minutos debido a un cambio de molde. Total de piezas aprobadas: 1200. Piezas rechazadas: 15 debido a defectos estéticos. El equipo de mantenimiento completó las revisiones preventivas en la M102. 
Líder de turno: Juan Pérez."""

FEW_SHOT_AI_EXAMPLE = """{
  "records": [
    {
      "machine_id": "M102",
      "downtime_minutes": 45,
      "approved_parts": 1200,
      "rejected_parts": 15,
      "reasons": ["cambio de molde", "defectos estéticos", "revisiones preventivas completadas"],
      "shift_leader": "Juan Pérez",
      "shift": "Turno 1"
    }
  ]
}"""


def is_ollama_available(url: str = OLLAMA_BASE_URL) -> bool:
    """Verifica de forma no bloqueante si el servidor de Ollama está accesible."""
    try:
        req = urllib.request.Request(f"{url}/api/tags", headers={"User-Agent": "rag-for-mails"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def sanitize_json_response(response_text: str) -> Dict[str, Any]:
    """
    Limpia y repara la respuesta del LLM eliminando bloques markdown,
    espacios innecesarios o envoltorios conversacionales.
    """
    cleaned = response_text.strip()
    
    # Eliminar bloques de código markdown ```json ... ```
    if "```" in cleaned:
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', cleaned, re.IGNORECASE)
        if match:
            cleaned = match.group(1).strip()

    # Si empieza después de algún texto explicativo
    json_start = cleaned.find('{')
    json_array_start = cleaned.find('[')
    
    if json_start != -1 and (json_array_start == -1 or json_start < json_array_start):
        json_end = cleaned.rfind('}')
        if json_end != -1:
            cleaned = cleaned[json_start:json_end + 1]
    elif json_array_start != -1:
        json_end = cleaned.rfind(']')
        if json_end != -1:
            raw_array = cleaned[json_array_start:json_end + 1]
            cleaned = f'{{"records": {raw_array}}}'

    data = json.loads(cleaned)

    # Si el LLM devolvió directamente un objeto de máquina individual
    if isinstance(data, dict) and "records" not in data and "machine_id" in data:
        data = {"records": [data]}
    elif isinstance(data, list):
        data = {"records": data}

    return data


class BaseExtractor:
    """Interfaz base para extractores de información de turnos."""
    def extract(self, raw_text: str, source_file: Optional[str] = None) -> ShiftReport:
        raise NotImplementedError


class OllamaShiftExtractor(BaseExtractor):
    """
    Extractor de información usando LangChain y modelos locales en Ollama (ej. qwen3:8b, llama3).
    """
    def __init__(self, model_name: str = OLLAMA_MODEL, base_url: str = OLLAMA_BASE_URL):
        self.model_name = model_name
        self.base_url = base_url
        self.llm = OllamaLLM(
            model=model_name,
            base_url=base_url,
            temperature=OLLAMA_TEMPERATURE,
            format="json"
        )
        self.prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=EXTRACTION_SYSTEM_PROMPT),
            HumanMessage(content=FEW_SHOT_USER_EXAMPLE),
            AIMessage(content=FEW_SHOT_AI_EXAMPLE),
            HumanMessagePromptTemplate.from_template("Analiza el siguiente reporte de turno y genera el JSON estructurado:\n\n{input_text}")
        ])
        self.chain = self.prompt | self.llm

    def extract(self, raw_text: str, source_file: Optional[str] = None) -> ShiftReport:
        response_text = self.chain.invoke({"input_text": raw_text})
        data = sanitize_json_response(response_text)
        validated_output = ExtractionOutput(**data)
        
        return ShiftReport(
            records=validated_output.records,
            raw_source=raw_text,
            source_file=source_file
        )


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
            # Caso de reporte de máquina única
            m_id = unique_machines[0]
            records.append(self._parse_machine_block(raw_text, m_id, shift, shift_leader))
        else:
            # Caso multi-máquina: segmentar por encabezado de máquina
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
                    if current_m:
                        current_lines.append(line)
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
        # Paro / Downtime
        down_match = re.search(r'(?:detenida durante|paro de|parada|fuera de servicio|tiempo detenido)?\s*:?\s*(\d+)\s*(?:minutos|min|m\b)', block, re.IGNORECASE)
        if not down_match:
            down_hour_match = re.search(r'(\d+)\s*(?:horas?|hrs?|h\b)', block, re.IGNORECASE)
            downtime = int(down_hour_match.group(1)) * 60 if down_hour_match else 0
        else:
            downtime = int(down_match.group(1))

        # Piezas aprobadas (soporta 'piezas aprobadas: 850' y '850 piezas aprobadas')
        appr_match = re.search(r'(?:piezas\s+(?:aprobadas|buenas|conformes)(?:\s+producidas)?|conformes|aprobadas)\s*[:=]?\s*(\d+)', block, re.IGNORECASE)
        if not appr_match:
            appr_match = re.search(r'(\d+)\s*(?:piezas\s+)?(?:aprobadas|buenas|conformes)', block, re.IGNORECASE)
        approved = int(appr_match.group(1)) if appr_match else 0

        # Piezas rechazadas (soporta 'rechazadas: 95', '95 rechazadas', 'scrap: 95')
        rej_match = re.search(r'(?:piezas\s+(?:rechazadas|defectuosas)|scrap|no\s+conformes|rechazadas)\s*(?:[/:=-]|\w+)*\s*[:=]?\s*(\d+)', block, re.IGNORECASE)
        if not rej_match:
            rej_match = re.search(r'(\d+)\s*(?:piezas\s+)?(?:rechazadas|defectuosas|scrap|no\s+conformes)', block, re.IGNORECASE)
        rejected = int(rej_match.group(1)) if rej_match else 0

        # Motivos
        reasons = []
        if "cambio de molde" in block.lower():
            reasons.append("cambio de molde")
        if "defectos estéticos" in block.lower():
            reasons.append("defectos estéticos")
        if "preventiva" in block.lower() or "mantenimiento" in block.lower() or "husillo" in block.lower():
            reasons.append("mantenimiento y revisiones")
        if "rebaba" in block.lower():
            reasons.append("rebabas en pieza")
        if "sensor" in block.lower() or "presión" in block.lower():
            reasons.append("falla sensor")
        if "temperatura" in block.lower() or "termopar" in block.lower() or "quemadura" in block.lower():
            reasons.append("ajuste térmico / quemadura")
        if "purga" in block.lower():
            reasons.append("purga de boquilla")
        if not reasons:
            reasons.append("operación regular")

        # Supervisor específico si existe en el bloque
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


def get_extractor(force_mock: bool = False) -> BaseExtractor:
    """
    Fábrica inteligente de extractores.
    Si Ollama está disponible y no se fuerza mock, utiliza OllamaShiftExtractor;
    en caso contrario, utiliza MockShiftExtractor.
    """
    if force_mock:
        return MockShiftExtractor()

    if is_ollama_available():
        return OllamaShiftExtractor()
    else:
        return MockShiftExtractor()
