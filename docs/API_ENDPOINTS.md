# 📡 Resumen de Endpoints y Argumentos (API)

Guía rápida de los endpoints del backend para conectar el frontend. Incluye únicamente los argumentos necesarios para peticiones exitosas.

**Base URL Local**: `http://localhost:8000` | **CORS**: Habilitado (`*`)

---

### 1. Diagnóstico del Sistema y Enlaces
* **Método**: `GET`
* **Ruta**: `/api/v1/system/status`
* **Argumentos**: Ninguno.
* **Respuesta Exitosa Clave**:
```json
{
  "status": "ok",
  "llm_provider": "gemini",
  "llm_model": "gemini-3.6-flash",
  "llm_available": true,
  "google_sheet_url": "https://docs.google.com/spreadsheets/d/1Qzlqx7mlAFc5jPRxL3MkPrBOHlQdxy9JDf0t0TxsE3Y/edit",
  "google_drive_folder_url": "https://drive.google.com/drive/folders/1O2hLAX0ypoCSng1wwTivfSNzTOAczqnq?hl=es"
}
```

---

### 2. Procesar Reporte (Extracción y Guardado)
Envía texto no estructurado para extraer registros de moldeo y guardarlos en Google Sheets y Excel.

* **Método**: `POST`
* **Ruta**: `/api/v1/process/text`
* **Headers**: `Content-Type: application/json`
* **Argumentos (Body)**:
```json
{
  "text": "Reporte del turno uno. La maquina M106 estuvo parada cuarenta minutos por falta de materia prima en tolva. Se fabricaron mil quinientas piezas aprobadas y doce piezas rechazadas por espesor irregular. Supervisor a cargo: Sofia Ramirez.",
  "force_mock": false,
  "source_name": "minifront"
}
```
> - `text` *(string, obligatorio)*: Texto del reporte.
> - `force_mock` *(boolean, opcional, default: `false`)*: `true` para procesar por regex sin llamar a la IA.
> - `source_name` *(string, opcional)*: Nombre de origen para auditoría.

* **Respuesta Exitosa Clave**:
```json
{
  "success": true,
  "records_extracted": 1,
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
  ],
  "google_sheet_url": "https://docs.google.com/spreadsheets/d/1Qzlqx7mlAFc5jPRxL3MkPrBOHlQdxy9JDf0t0TxsE3Y/edit"
}
```

---

### 3. Listar Proveedores y Modelos de IA
Para llenar los selectores desplegables en la interfaz.

* **Método**: `GET`
* **Ruta**: `/api/v1/ai/models`
* **Argumentos**: Ninguno.
* **Respuesta Exitosa Clave**:
```json
{
  "active_provider": "gemini",
  "active_model": "gemini-3.6-flash",
  "is_available": true,
  "supported_providers": {
    "gemini": { "available": true, "default_model": "gemini-3.6-flash", "models": ["gemini-3.6-flash", "gemini-1.5-flash", "gemini-1.5-pro"] },
    "openai": { "available": false, "default_model": "gpt-4o-mini", "models": ["gpt-4o-mini", "gpt-4o"] },
    "anthropic": { "available": false, "default_model": "claude-3-5-sonnet-20240620", "models": ["claude-3-5-sonnet-20240620"] },
    "ollama": { "available": false, "default_model": "qwen3:8b", "models": ["qwen3:8b", "llama3:8b"] }
  }
}
```

---

### 4. Cambiar Proveedor o Modelo de IA
Cambia en caliente el proveedor activo o su modelo.

* **Método**: `POST`
* **Ruta**: `/api/v1/ai/models`
* **Headers**: `Content-Type: application/json`
* **Argumentos (Body)**:
```json
{
  "provider": "gemini",
  "model": "gemini-3.6-flash"
}
```
* **Respuesta Exitosa Clave**:
```json
{
  "success": true,
  "active_provider": "gemini",
  "active_model": "gemini-3.6-flash",
  "message": "Configuración de IA actualizada a 'gemini' (modelo: 'gemini-3.6-flash')."
}
```

---

### 5. Simular Correo de Gmail
Prueba la ingesta simulando la llegada de un correo.

* **Método**: `POST`
* **Ruta**: `/api/v1/webhook/gmail`
* **Headers**: `Content-Type: application/json`
* **Argumentos (Body)**:
```json
{
  "simulate": true,
  "raw_text": "Turno 2: Máquina M105: 850 piezas aprobadas, 95 rechazadas. Paro de 75 minutos. Líder: Maria Rodriguez"
}
```
* **Respuesta Exitosa Clave**:
```json
{
  "success": true,
  "mode": "simulation",
  "processed_count": 1,
  "google_sheet_url": "https://docs.google.com/spreadsheets/d/1Qzlqx7mlAFc5jPRxL3MkPrBOHlQdxy9JDf0t0TxsE3Y/edit"
}
```

---

### 6. Control de Suscripción Gmail Push
- **Activar**: `POST /api/v1/webhook/gmail/watch?topic_name=projects/TU_PROYECTO/topics/TU_TOPIC`
  - Argumento (Query param): `topic_name`
- **Detener**: `POST /api/v1/webhook/gmail/stop-watch`
  - Argumentos: Ninguno.
