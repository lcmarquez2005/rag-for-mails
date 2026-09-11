# rag-for-mails 🏭

Sistema automatizado de extracción, validación estricta y sincronización de reportes operativos no estructurados enviados por correo o chat en plantas de moldeo por inyección.

Construido con **Python**, **FastAPI**, **Pydantic V2** y soporte multiproveedor de IA (**Ollama**, **OpenAI**, **Google Gemini**, **Anthropic Claude**).

---

## 🎯 Entregables del Proyecto

1. 📄 [**Especificación del Prompt de Extracción (docs/PROMPT.md)**](docs/PROMPT.md)
   * Prompt exacto de sistema, Few-Shot guidance, esquema JSON formal y manejo de casos borde (unidades de tiempo, scrap, multi-máquina).
2. 📄 [**Documento de Arquitectura E2E y Prevención de Corrupción (docs/ARQUITECTURA_AUTOMATIZACION.md)**](docs/ARQUITECTURA_AUTOMATIZACION.md)
   * Stack técnico, pipeline de ingesta, capa de validación con Pydantic V2, Dead Letter Queue y persistencia en `output.json`.
3. 📄 [**Integración de Webhook de Gmail y Event-Driven (docs/INTEGRACION_WEBHOOK_GMAIL.md)**](docs/INTEGRACION_WEBHOOK_GMAIL.md)
   * Arquitectura del Webhook FastAPI, integración con Google Cloud Pub/Sub, endpoints, payloads, simulación y guía de despliegue en producción.
4. 📄 [**Especificación de Endpoints y Payloads para Frontend (docs/API_ENDPOINTS.md)**](docs/API_ENDPOINTS.md)
   * Catálogo completo de endpoints, payloads JSON, modelos TypeScript y ejemplos de consumo para el desarrollo de minifrontends.

---

## 🚀 Inicio Rápido con FastAPI

### 1. Instalación de Dependencias
```bash
poetry install
```

### 2. Iniciar el Servidor FastAPI
Para iniciar el servidor en modo desarrollo con recarga automática:
```bash
poetry run python main.py
```
o directamente con uvicorn:
```bash
poetry run uvicorn src.api.app:app --reload --port 8000
```
La documentación interactiva de Swagger UI estará disponible en:
👉 `http://127.0.0.1:8000/docs`

---

### 🐳 Despliegue con Docker (Opcional)

Puedes construir y ejecutar el contenedor fácilmente con Docker o Docker Compose:

**Con Docker Compose (Recomendado):**
```bash
# Construir y levantar el contenedor en segundo plano
docker compose up -d --build

# Ver registros en tiempo real
docker compose logs -f

# Detener el contenedor
docker compose down
```

**Con Docker CLI directo:**
```bash
# Construir la imagen
docker build -t rag-for-mails:latest .

# Ejecutar el contenedor persistiendo los datos de salida
docker run -d \
  --name rag-for-mails-api \
  -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/data/output:/app/data/output \
  rag-for-mails:latest
```

---

## 📡 Endpoints de la API

### 1. `GET /health`
Verifica el estado del servicio, Ollama y las rutas de persistencia en el servidor.
```bash
curl -X GET "http://localhost:8000/health"
```

### 2. `POST /api/v1/process/text`
Envía texto no estructurado directamente. El reporte extraído actualiza de inmediato el archivo Excel (`data/output/reporte_moldeo.xlsx`) y JSON (`data/output/output.json`) **únicamente en el servidor**.

**Opción A: Vía JSON**
```bash
curl -X POST "http://localhost:8000/api/v1/process/text" \
     -H "Content-Type: application/json" \
     -d '{
       "text": "Actualización del Turno 1:\nLa máquina M102 estuvo detenida durante 45 minutos debido a un cambio de molde. Total de piezas aprobadas: 1200. Piezas rechazadas: 15 debido a defectos estéticos.\nLíder de turno: Juan Pérez.",
       "force_mock": true
     }'
```

**Opción B: Vía texto plano directo**
```bash
curl -X POST "http://localhost:8000/api/v1/process/text?force_mock=true" \
     -H "Content-Type: text/plain" \
     --data-binary "Turno 2: Máquina M105: 850 piezas aprobadas, 95 rechazadas. Paro de 75 minutos. Líder: Maria Rodriguez"
```

### 3. `POST /api/v1/webhook/gmail`
Webhook preparado para recibir notificaciones push de Google Cloud Pub/Sub o ejecutar simulaciones de prueba local directa:

**Simulación local directa:**
```bash
curl -X POST "http://localhost:8000/api/v1/webhook/gmail" \
     -H "Content-Type: application/json" \
     -d '{
       "simulate": true,
       "raw_text": "Turno 1: Máquina M102 estuvo detenida durante 45 min por cambio de molde. Aprobadas: 1200, rechazadas: 15. Líder: Juan Pérez",
       "force_mock": true
     }'
```


---

## 🤖 Configuración Multiproveedor de Inteligencia Artificial

El sistema soporta indistintamente proveedores locales y en la nube mediante variables de entorno en `.env`:

| Proveedor | Variable `LLM_PROVIDER` | Modelo Predeterminado | Clave / URL Requerida |
| :--- | :--- | :--- | :--- |
| **Ollama (Local)** | `ollama` | `qwen3:8b` | `OLLAMA_BASE_URL` (defecto: `http://localhost:11434`) |
| **OpenAI** | `openai` | `gpt-4o-mini` | `OPENAI_API_KEY` (opcional: `OPENAI_BASE_URL`) |
| **Google Gemini** | `gemini` | `gemini-2.5-flash` | `GEMINI_API_KEY` o `GOOGLE_API_KEY` |
| **Anthropic Claude** | `anthropic` o `claude` | `claude-3-5-sonnet-20240620` | `ANTHROPIC_API_KEY` |

### Endpoint de Gestión Dinámica de Modelos (`/api/v1/ai/models`)

1. **Consultar proveedores y modelos soportados (GET)**:
```bash
curl -X GET "http://localhost:8000/api/v1/ai/models"
```
Retorna el catálogo completo con los modelos disponibles (`gemini-2.5-flash`, `gemini-1.5-pro`, `gpt-4o`, `claude-3-7-sonnet`, `qwen3:8b`, etc.), si requieren API Key y cuál está actualmente activo.

2. **Cambiar el modelo activo en caliente (POST)**:
```bash
# Cambiar a Gemini Pro
curl -X POST "http://localhost:8000/api/v1/ai/models" \
     -H "Content-Type: application/json" \
     -d '{
       "provider": "gemini",
       "model": "gemini-1.5-pro",
       "api_key": "TU_GEMINI_API_KEY"
     }'
```

3. **Sobrescribir el proveedor por petición**:
```json
{
  "text": "Actualización del Turno 1: Máquina M102...",
  "llm_provider": "gemini",
  "llm_model": "gemini-1.5-pro"
}
```

---

## 🧪 Ejecución de Pruebas Unitarias

Para ejecutar la suite completa de pruebas automatizadas:
```bash
poetry run pytest tests/ -v
```

---

## 📁 Estructura del Repositorio

```
rag-for-mails/
├── docs/
│   ├── ARQUITECTURA_COMPLETA.md       # Arquitectura integral E2E (AWS, Webhook, IA, Pydantic)
│   ├── PROMPT.md                      # Entregable 1: Prompt exacto y esquema
│   ├── ARQUITECTURA_AUTOMATIZACION.md # Entregable 2: Arquitectura y anti-corrupción
│   └── INTEGRACION_WEBHOOK_GMAIL.md   # Entregable 3: Integración Gmail Pub/Sub
├── data/
│   ├── sample_mails/                  # Archivos de correo de prueba (.txt)
│   └── output/                        # Reportes generados (Excel, JSON y DLQ)
├── src/
│   ├── config.py                      # Configuración central (IA, Gmail, servidor)
│   ├── extractor.py                   # Extractor multiproveedor LLMShiftExtractor / Mock
│   ├── exporters.py                   # Exportadores optimizados a JSON, Excel y Google Sheets
│   ├── sheets_client.py               # Cliente oficial Google Sheets API v4 con formato corporativo
│   ├── pipeline.py                    # Orquestador del flujo E2E
│   ├── gmail_client.py                # Cliente oficial de Gmail API
│   ├── schemas/                       # Esquemas Pydantic V2 (reports.py, api.py)
│   ├── services/                      # Servicios de negocio desacoplados
│   │   ├── ai/                        # Módulo multiproveedor de IA
│   │   │   ├── prompts.py             # Prompts del sistema y ejemplos few-shot
│   │   │   ├── providers.py           # Adaptadores para Ollama, OpenAI, Gemini y Claude
│   │   │   └── service.py             # Orquestador LLMService y sanitización JSON
│   │   ├── health_service.py          # Chequeo de estado del sistema, IA y Google Sheets
│   │   ├── report_service.py          # Extracción y validación de texto
│   │   └── webhook_service.py         # Manejo de Webhooks, deduplicación y watch()
│   └── api/
│       └── app.py                     # Servidor FastAPI y enrutamiento
├── main.py                            # Entrypoint de arranque del servidor
├── pyproject.toml                     # Definición de dependencias Poetry
└── tests/                             # Suite de pruebas unitarias e integración (45 tests)
```
