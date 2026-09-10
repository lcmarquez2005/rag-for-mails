# rag-for-mails 🏭

Sistema automatizado de extracción, validación estricta y sincronización de reportes operativos no estructurados enviados por correo o chat en plantas de moldeo por inyección.

Construido con **Python**, **LangChain**, **Ollama (`qwen3:8b`)**, **Pydantic V2** y **Rich**.

---

## 🎯 Entregables del Proyecto

1. 📄 [**Especificación del Prompt de Extracción (docs/PROMPT.md)**](docs/PROMPT.md)
   * Prompt exacto de sistema, Few-Shot guidance, esquema JSON formal y manejo de casos borde (unidades de tiempo, scrap, multi-máquina).
2. 📄 [**Documento de Arquitectura E2E y Prevención de Corrupción (docs/ARQUITECTURA_AUTOMATIZACION.md)**](docs/ARQUITECTURA_AUTOMATIZACION.md)
   * Stack técnico, pipeline de ingesta, capa de validación con Pydantic V2, Dead Letter Queue y persistencia en `output.json`.
3. 📄 [**Integración de Webhook de Gmail y Event-Driven (docs/INTEGRACION_WEBHOOK_GMAIL.md)**](docs/INTEGRACION_WEBHOOK_GMAIL.md)
   * Arquitectura del Webhook FastAPI, integración con Google Cloud Pub/Sub, endpoints, payloads, simulación y guía de despliegue en producción.

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

## 🧪 Ejecución de Pruebas Unitarias

Para ejecutar la suite de pruebas automatizadas con Pytest:
```bash
poetry run pytest tests/ -v
```

---

## 📁 Estructura del Repositorio

```
rag-for-mails/
├── docs/
│   ├── PROMPT.md                      # Entregable 1: Prompt exacto y esquema
│   └── ARQUITECTURA_AUTOMATIZACION.md # Entregable 2: Arquitectura y anti-corrupción
├── data/
│   ├── sample_mails/                  # Archivos de correo de prueba (.txt)
│   │   ├── turno1_estandar.txt        # Caso del README
│   │   ├── turno2_scrap_alto.txt      # Caso con anomalía de piezas
│   │   ├── turno3_multimaquina.txt    # Caso con múltiples máquinas
│   │   └── turno3_paro_prolongado.txt # Caso con paro mayor
│   └── output/                        # Reportes generados
│       ├── reporte_moldeo.xlsx        # Reporte Excel consolidado con los datos extraídos
│       ├── output.json                # JSON estructurado con la especificación original
│       └── quarantine.json            # Dead Letter Queue para entradas erróneas
├── src/
│   ├── config.py                      # Configuración de Ollama, API y rutas
│   ├── schemas.py                     # Modelos Pydantic V2 de negocio
│   ├── extractor.py                   # Extractor LangChain + Ollama / Mock
│   ├── exporters.py                   # Exportador JSON y Excel
│   ├── pipeline.py                    # Orquestador del flujo E2E
│   ├── gmail_client.py                # Cliente oficial de Gmail API
│   ├── services/                      # Capa de servicios (lógica de negocio desacoplada)
│   │   ├── health_service.py          # Chequeo de estado del sistema
│   │   ├── report_service.py          # Lógica de extracción de reportes de texto
│   │   └── webhook_service.py         # Lógica de eventos Pub/Sub, deduplicación y watch
│   └── api/
│       ├── app.py                     # API FastAPI limpia (enrutamiento hacia servicios)
│       └── schemas.py                 # Modelos Pydantic para peticiones y respuestas
├── main.py                            # Entrypoint de arranque del servidor FastAPI
├── pyproject.toml                     # Definición de dependencias Poetry
└── tests/
    ├── test_all.py                    # Pruebas unitarias de extractor y pipeline
    ├── test_gmail.py                  # Pruebas unitarias del cliente de Gmail
    └── test_api.py                    # Pruebas unitarias de endpoints FastAPI
```
