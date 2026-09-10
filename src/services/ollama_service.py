import json
import re
import urllib.request
import logging
from typing import Dict, Any, Optional

from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_ollama import OllamaLLM

from src.config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TEMPERATURE

logger = logging.getLogger("rag_mails.services.ollama")

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


def is_ollama_available(url: Optional[str] = None) -> bool:
    """Verifica de forma no bloqueante si el servidor de Ollama está accesible."""
    target_url = url or OLLAMA_BASE_URL
    try:
        req = urllib.request.Request(f"{target_url}/api/tags", headers={"User-Agent": "rag-for-mails"})
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

    # Extraer el bloque JSON principal
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

    if isinstance(data, dict) and "records" not in data and "machine_id" in data:
        data = {"records": [data]}
    elif isinstance(data, list):
        data = {"records": data}

    return data


class OllamaService:
    """
    Servicio de conexión, orquestación y consulta al modelo local Ollama
    utilizando LangChain y prompts optimizados para manufactura.
    """
    def __init__(
        self,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None
    ):
        self.model_name = model_name or OLLAMA_MODEL
        self.base_url = base_url or OLLAMA_BASE_URL
        self.temperature = temperature if temperature is not None else OLLAMA_TEMPERATURE
        self._llm: Optional[OllamaLLM] = None
        self._chain = None

    @property
    def is_online(self) -> bool:
        return is_ollama_available(self.base_url)

    def _get_chain(self):
        if self._chain is None:
            self._llm = OllamaLLM(
                model=self.model_name,
                base_url=self.base_url,
                temperature=self.temperature,
                format="json"
            )
            prompt = ChatPromptTemplate.from_messages([
                SystemMessage(content=EXTRACTION_SYSTEM_PROMPT),
                HumanMessage(content=FEW_SHOT_USER_EXAMPLE),
                AIMessage(content=FEW_SHOT_AI_EXAMPLE),
                HumanMessagePromptTemplate.from_template("Analiza el siguiente reporte de turno y genera el JSON estructurado:\n\n{input_text}")
            ])
            self._chain = prompt | self._llm
        return self._chain

    def invoke_extraction(self, raw_text: str) -> Dict[str, Any]:
        """Envía el texto al modelo y retorna el diccionario estructurado limpio."""
        chain = self._get_chain()
        response_text = chain.invoke({"input_text": raw_text})
        return sanitize_json_response(response_text)
