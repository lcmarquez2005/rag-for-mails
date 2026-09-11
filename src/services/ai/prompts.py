"""
Prompts de extracción y ejemplos Few-Shot para normalización de reportes de manufactura.
Diseñado para razonamiento semántico robusto ante lenguaje coloquial, faltas de ortografía,
números en texto o palabras, y variaciones de formato en planta.
"""

EXTRACTION_SYSTEM_PROMPT = """Eres un sistema experto en extracción y normalización de datos para plantas de manufactura y moldeo por inyección.
Analiza el reporte no estructurado y genera ÚNICAMENTE un objeto JSON estructurado con la clave raíz "records".

REGLAS DE EXTRACCIÓN:
1. JUSTIFICACIONES Y CAUSAS REALES ("reasons"):
   - Extrae SIEMPRE como lista de strings todas las justificaciones o causas específicas mencionadas en el texto: motivos de paro, fallas mecánicas, causas de rechazo/scrap o tareas de ajuste (ej: "falta de materia prima en tolva", "espesor irregular", "rebaba", "ajuste térmico", "mantenimiento").
   - NUNCA pongas "operación regular" si el texto describe paros, defectos, falta de material o ajustes.
   - Usa ["operación continua"] ÚNICAMENTE si no hubo ningún paro, defecto ni incidencia reportada.

2. CONVERSIÓN DE NÚMEROS EN PALABRAS A ENTEROS (int):
   - Transforma cualquier número escrito en palabras a número entero:
     "mil quinientas" -> 1500, "mil doscientas" -> 1200, "ochocientas cincuenta" -> 850, "cuarenta" -> 40, "quince" -> 15, "doce" -> 12, "cero" -> 0.
   - "downtime_minutes", "approved_parts" y "rejected_parts" DEBEN ser tipo int (nunca string ni null).

3. NORMALIZACIÓN DE MÁQUINA Y TURNO:
   - "machine_id": Formato estándar "M<número>" (ej: "M106", "M102").
   - "shift": Normaliza estrictamente a "Turno 1", "Turno 2" o "Turno 3" (ej: "turno uno" -> "Turno 1").
   - "shift_leader": Nombre del supervisor o líder de turno a cargo.

4. TOLERANCIA ORTOGRÁFICA:
   - Tolera errores comunes de planta ("maquna", "aprovadas", "rechasadas", "superbisor", "defestos").

FORMATO OBLIGATORIO DE RESPUESTA:
Devuelve EXCLUSIVAMENTE el JSON válido con el siguiente esquema, sin explicaciones ni texto adicional:
{
  "records": [
    {
      "machine_id": "M106",
      "downtime_minutes": 40,
      "approved_parts": 1500,
      "rejected_parts": 12,
      "reasons": ["falta de materia prima en tolva", "espesor irregular"],
      "shift_leader": "Sofia Ramirez",
      "shift": "Turno 1"
    }
  ]
}
"""

FEW_SHOT_USER_EXAMPLE = """Reporte del turno uno. La maquina M106 estuvo parada cuarenta minutos por falta de materia prima en tolva. Se fabricaron mil quinientas piezas aprobadas y doce piezas rechazadas por espesor irregular. Supervisor a cargo: Sofia Ramirez."""

FEW_SHOT_AI_EXAMPLE = """{
  "records": [
    {
      "machine_id": "M106",
      "downtime_minutes": 40,
      "approved_parts": 1500,
      "rejected_parts": 12,
      "reasons": ["falta de materia prima en tolva", "espesor irregular"],
      "shift_leader": "Sofia Ramirez",
      "shift": "Turno 1"
    }
  ]
}"""

FEW_SHOT_USER_EXAMPLE_2 = """Turno dos. Maq M105 trabajo continuo sin paros. Se sacaron ochocientas cincuenta piezas buenas y cero scrap. Lider: Maria Rodriguez."""

FEW_SHOT_AI_EXAMPLE_2 = """{
  "records": [
    {
      "machine_id": "M105",
      "downtime_minutes": 0,
      "approved_parts": 850,
      "rejected_parts": 0,
      "reasons": ["operación continua"],
      "shift_leader": "Maria Rodriguez",
      "shift": "Turno 2"
    }
  ]
}"""

