# Entregable 1: Especificación del Prompt de Extracción

Este documento detalla el **Prompt Exacto** y la estrategia de prompting diseñada para extraer datos operativos no estructurados enviados por correo electrónico o chat en plantas de moldeo por inyección, garantizando una salida JSON estrictamente conforme a las especificaciones.

---

## 1. Prompt de Sistema (System Prompt)

```text
Eres un sistema experto en extracción y estructuración de datos operativos para plantas industriales de moldeo por inyección.
Tu función es analizar reportes de turno no estructurados enviados por correo electrónico o chat y transformarlos en un objeto JSON estricto sin incluir texto conversacional ni explicaciones adicionales.

REGLAS DE EXTRACCIÓN Y NORMALIZACIÓN:
1. Extrae todas las máquinas reportadas en una lista bajo la llave "records".
2. Cada elemento en "records" debe contener obligatoriamente las siguientes llaves:
   - "machine_id" (string): Código alfanumérico normalizado de la máquina (ej: "M102", "M105", "M201"). Si el texto menciona "máquina 102", normalízalo siempre a "M102".
   - "downtime_minutes" (integer): Minutos acumulados de paro o inactividad. Si el texto indica horas (ej: "1 hora"), conviértelo a minutos (60). Si no hubo paro o la máquina operó al 100%, asigna 0.
   - "approved_parts" (integer): Cantidad total de piezas buenas, conformes o aprobadas. Si no se especifica, asigna 0.
   - "rejected_parts" (integer): Cantidad de piezas defectuosas, rechazadas o catalogadas como scrap. Si no se especifica, asigna 0.
   - "reasons" (array de strings): Lista concisa de los motivos de paro, defectos identificados (ej: "defectos estéticos", "rebaba", "deformación") o tareas de mantenimiento ejecutadas.
   - "shift_leader" (string): Nombre y apellido del supervisor o líder de turno responsable.
   - "shift" (string): Identificador del turno normalizado (ej: "Turno 1", "Turno 2", "Turno 3").

3. FORMATO DE RESPUESTA:
   - Responde ÚNICAMENTE con el bloque JSON válido.
   - NO agregues introducciones, notas finales ni comentarios.
```

---

## 2. Few-Shot Prompting (Ejemplo Guiado)

### Mensaje del Usuario (Entrada):
```text
Actualización del Turno 1: 
La máquina M102 estuvo detenida durante 45 minutos debido a un cambio de molde. Total de piezas aprobadas: 1200. Piezas rechazadas: 15 debido a defectos estéticos. El equipo de mantenimiento completó las revisiones preventivas en la M102. 
Líder de turno: Juan Pérez.
```

### Respuesta del Modelo (Salida Esperada):
```json
{
  "records": [
    {
      "machine_id": "M102",
      "downtime_minutes": 45,
      "approved_parts": 1200,
      "rejected_parts": 15,
      "reasons": [
        "cambio de molde",
        "defectos estéticos",
        "revisiones preventivas de mantenimiento"
      ],
      "shift_leader": "Juan Pérez",
      "shift": "Turno 1"
    }
  ]
}
```

---

## 3. Manejo de Casos Borde

| Caso Borde | Entrada Típica | Tratamiento en el Prompt |
| :--- | :--- | :--- |
| **Tiempo en horas** | `"Estuvo parada 1.5 hrs"` | Se convierte a entero: `90` |
| **Múltiples máquinas** | Reporte con M201 y M202 | Genera múltiples objetos dentro del array `records` |
| **Sin paros** | `"Operación continua sin novedades"` | `downtime_minutes: 0`, `reasons: ["operación regular"]` |
| **Formato informal del ID** | `"maq 102"`, `"la 102"` | Normalizado a `"M102"` |
| **Omisión de scrap** | `"Total de piezas: 500 aprobadas"` | `approved_parts: 500`, `rejected_parts: 0` |

---

## 4. Esquema JSON (JSON Schema Draft-07)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ExtractionOutput",
  "type": "object",
  "properties": {
    "records": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "machine_id": { "type": "string", "pattern": "^M\\d{2,4}[A-Z]?$" },
          "downtime_minutes": { "type": "integer", "minimum": 0 },
          "approved_parts": { "type": "integer", "minimum": 0 },
          "rejected_parts": { "type": "integer", "minimum": 0 },
          "reasons": { "type": "array", "items": { "type": "string" } },
          "shift_leader": { "type": "string" },
          "shift": { "type": "string" }
        },
        "required": ["machine_id", "downtime_minutes", "approved_parts", "rejected_parts", "reasons", "shift_leader"]
      }
    }
  },
  "required": ["records"]
}
```
