# Sistema Inteligente de Extracción y Reportes de Moldeo (RAG for Mails) 🏭

Plataforma empresarial para la **ingesta automatizada, extracción con inteligencia artificial, validación estricta y sincronización en tiempo real** de reportes operativos de producción en plantas de moldeo por inyección y manufactura plástica.

El sistema transforma mensajes no estructurados (correos electrónicos de turno, reportes de supervisores o chats de planta)—incluso con lenguaje coloquial, abreviaturas, faltas ortográficas o cantidades expresadas en palabras—en registros normalizados y los sincroniza de inmediato tanto en un **Google Sheet maestro corporativo en Google Drive** como en archivos **Excel y JSON locales**.

---

## 🎯 Capacidades Principales

- **Extracción Semántica con LLM**: Motor de inferencia multiproveedor compatible con **Google Gemini** (predeterminado: `gemini-3.6-flash`), **OpenAI** (`gpt-4o-mini`), **Anthropic Claude** (`claude-3-5-sonnet`) y modelos locales mediante **Ollama** (`qwen3:8b`).
- **Tolerancia a Lenguaje Real de Planta**:
  - Conversión estricta de números escritos en palabras a enteros (`"mil quinientas"` $\rightarrow$ `1500`, `"cuarenta y cinco minutos"` $\rightarrow$ `45`, `"quince"` $\rightarrow$ `15`, `"sin scrap"` $\rightarrow$ `0`).
  - Tolerancia fonética y ortográfica ante términos habituales de planta (`"aprovadas"`, `"rechasadas"`, `"maquna"`, `"superbisor"`, `"defestos"`).
  - Extracción fiel de las justificaciones y causas de paro o rechazo en el campo `reasons` (`"falta de materia prima en tolva"`, `"espesor irregular"`).
  - Normalización estricta de nomenclatura para turnos (`"Turno 1"`, `"Turno 2"`, `"Turno 3"`) y máquinas (`"M102"`, `"M106"`).
- **Sincronización en Tiempo Real con Google Sheets**:
  - Conexión oficial mediante Google Sheets API v4 en la carpeta designada de Google Drive (*Reportes de Moldeo*).
  - Formato corporativo idéntico a Excel: cabecera en azul marino institucional (`#1F4E79`), tipografía blanca en negrita, primera fila inmovilizada (*frozen row*) y bordes finos.
  - Deduplicación idempotente basada en el par `(ID Correo / Origen, Máquina ID)` para evitar registros repetidos ante reintentos de red.
- **Validación Estricta de Esquemas**: Garantía de integridad de datos mediante modelos fuertemente tipados con **Pydantic V2**.
- **Arquitectura Event-Driven (Gmail API & Webhooks)**: Soporte para notificaciones push de Google Cloud Pub/Sub y simulación directa de correos entrantes.

---

## 🐳 Ejecución y Despliegue con Docker

La aplicación está completamente dockerizada sobre imágenes optimizadas basadas en `python:3.12-slim-bookworm` con servidor ASGI **Uvicorn** de alto rendimiento y healthchecks integrados.

### 1. Requisitos Previos
- [Docker Engine](https://docs.docker.com/engine/install/) $\ge$ 24.0 o [Docker Desktop](https://www.docker.com/products/docker-desktop/).
- Archivo de variables de entorno [`.env`](.env) configurado (puedes basarte en [`.env.example`](.env.example)).
- Archivos de autenticación de Google ([`credentials.json`](credentials.json) y [`token.json`](token.json)) en la raíz del proyecto para la sincronización con Google Sheets y Gmail.

---

### 2. Ejecución con Docker Compose (Recomendado)

Docker Compose gestiona automáticamente el mapeo de puertos, volúmenes de persistencia y variables de entorno:

```bash
# 1. Construir la imagen y levantar el contenedor en segundo plano
docker compose up -d --build

# 2. Monitorear los registros (logs) en tiempo real
docker compose logs -f

# 3. Detener los servicios
docker compose down
```

---

### 3. Ejecución con Docker CLI Directo

Si prefieres gestionar el contenedor directamente desde la línea de comandos:

#### A. Construir la Imagen Docker
```bash
docker build -t ia-reportes-moldeo:latest .
```

#### B. Iniciar el Contenedor
Monta el archivo `.env`, los tokens de Google y la carpeta de salida local para asegurar la persistencia:

```bash
docker run -d \
  --name rag-mails-app \
  -p 8000:8000 \
  --env-file .env \
  -v "$(pwd)/token.json:/app/token.json:ro" \
  -v "$(pwd)/credentials.json:/app/credentials.json:ro" \
  -v "$(pwd)/data/output:/app/data/output" \
  ia-reportes-moldeo:latest
```

#### C. Comandos Operativos de Docker
```bash
# Inspeccionar estado y healthcheck
docker ps

# Ver registros de ejecución
docker logs -f rag-mails-app

# Detener o reiniciar el contenedor
docker stop rag-mails-app
docker start rag-mails-app

# Eliminar el contenedor
docker rm -f rag-mails-app
```

---

### 4. Verificación del Servicio en Contenedor

Una vez iniciado el contenedor, verifica que el servicio esté respondiendo correctamente:

```bash
# Healthcheck ligero
curl -i http://localhost:8000/health

# Diagnóstico integral del sistema, estado del LLM y enlace de Google Sheets
curl -s http://localhost:8000/api/v1/system/status
```

Documentación interactiva disponible en el navegador:
👉 **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)  
👉 **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## ⚙️ Configuración del Entorno (`.env`)

Copia la plantilla base si configuras un nuevo entorno:
```bash
cp .env.example .env
```

Variables esenciales:

| Variable | Descripción | Valor Ejemplo |
| :--- | :--- | :--- |
| `LLM_PROVIDER` | Proveedor activo de IA (`gemini`, `openai`, `anthropic`, `ollama`) | `gemini` |
| `GEMINI_API_KEY` | Clave de API de Google AI Studio | `AIzaSy...` |
| `GEMINI_MODEL` | Modelo de lenguaje de Google Gemini | `gemini-3.6-flash` |
| `EXPORT_TARGET` | Destino de exportación (`both`, `sheets`, `excel`) | `both` |
| `GOOGLE_SHEET_ID` | Identificador del archivo Google Sheets maestro | `1Qzlqx7mlAFc5jPRxL3MkPrBOHlQdxy9JDf0t0TxsE3Y` |
| `GOOGLE_DRIVE_FOLDER_ID` | Carpeta de Google Drive para los reportes | `1O2hLAX0ypoCSng1wwTivfSNzTOAczqnq` |
| `GMAIL_AUTHORIZED_SENDER` | Remitente autorizado para procesar correos | `planta@empresa.com` |

---

## 💻 Ejecución Local con Python / Poetry (Sin Docker)

Si deseas ejecutar o desarrollar directamente en tu entorno Python local:

```bash
# 1. Instalar dependencias con Poetry
poetry install

# 2. Iniciar el servidor FastAPI con recarga automática
poetry run uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```

---

## 📡 Endpoints Principales de la API

| Método | Ruta | Descripción | Payload Resumido |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Healthcheck básico para balanceadores (AWS ALB/ECS) | Ninguno |
| `GET` | `/api/v1/system/status` | Diagnóstico de IA, Google Sheets y rutas de salida | Ninguno |
| `POST` | `/api/v1/process/text` | Extracción de reporte desde texto no estructurado | `{"text": "Reporte de turno..."}` |
| `GET` | `/api/v1/ai/models` | Listado de proveedores y modelos disponibles | Ninguno |
| `POST` | `/api/v1/ai/models` | Cambio dinámico de proveedor/modelo en caliente | `{"provider": "gemini", "model": "..."}` |
| `POST` | `/api/v1/webhook/gmail` | Recepción de notificaciones push o simulación | `{"simulate": true, "raw_text": "..."}` |

> 📖 Para una guía completa de argumentos, modelos TypeScript y ejemplos para conectar un frontend, consulta [`docs/API_ENDPOINTS.md`](docs/API_ENDPOINTS.md).

---

## 🧪 Suite de Pruebas Automatizadas

El proyecto cuenta con una cobertura integral de pruebas unitarias y de integración que validan el pipeline, la lógica de negocio, clientes de Google Sheets/Gmail y adaptadores de IA:

```bash
# Ejecutar todas las pruebas con pytest
poetry run pytest tests/ -v
```

**Resultado actual:** **47 pruebas pasando al 100%**.

---

## 📚 Documentación Técnica Adicional

- [**Resumen de Endpoints para Frontend (docs/API_ENDPOINTS.md)**](docs/API_ENDPOINTS.md): Especificación rápida de rutas y argumentos para el desarrollo de interfaces de usuario.
- [**Especificación del Prompt de Extracción (docs/PROMPT.md)**](docs/PROMPT.md): Instrucciones de sistema, ejemplos Few-Shot y resolución de casos límite de planta.
- [**Plan de Migración e Integración Google Sheets (docs/PLAN_MIGRACION_GOOGLE_SHEETS.md)**](docs/PLAN_MIGRACION_GOOGLE_SHEETS.md): Detalle de la integración en la nube con Google Drive y AWS ECS.
- [**Arquitectura de Automatización y Anti-Corrupción (docs/ARQUITECTURA_AUTOMATIZACION.md)**](docs/ARQUITECTURA_AUTOMATIZACION.md): Mecanismos de validación Pydantic V2, Dead Letter Queue y serialización.
- [**Integración de Webhook con Gmail (docs/INTEGRACION_WEBHOOK_GMAIL.md)**](docs/INTEGRACION_WEBHOOK_GMAIL.md): Arquitectura event-driven con Google Cloud Pub/Sub.

---

## 📁 Estructura del Repositorio

```
rag-for-mails/
├── docs/                               # Documentación arquitectónica y operativa
│   ├── API_ENDPOINTS.md                # Endpoints y payloads para frontend
│   ├── PLAN_MIGRACION_GOOGLE_SHEETS.md # Integración con Google Sheets y Drive
│   ├── PROMPT.md                       # Especificación del prompt de extracción
│   ├── ARQUITECTURA_AUTOMATIZACION.md  # Arquitectura E2E y prevención de corrupción
│   └── INTEGRACION_WEBHOOK_GMAIL.md    # Integración con Gmail y Google Cloud Pub/Sub
├── data/
│   ├── sample_mails/                   # Muestras de correos de prueba (.txt)
│   └── output/                         # Archivos generados (reporte_moldeo.xlsx, output.json)
├── src/
│   ├── api/
│   │   └── app.py                      # Aplicación FastAPI y definición de rutas
│   ├── schemas/                        # Modelos Pydantic V2 (reports.py, api.py)
│   ├── services/
│   │   ├── ai/                         # Módulo de IA (prompts, providers, service)
│   │   ├── health_service.py           # Servicio de diagnóstico del sistema
│   │   ├── report_service.py           # Orquestación de procesamiento de reportes
│   │   └── webhook_service.py          # Lógica de Webhook de Gmail y deduplicación
│   ├── config.py                       # Configuración central del sistema
│   ├── sheets_client.py                # Cliente oficial de Google Sheets API v4
│   ├── gmail_client.py                 # Cliente de Google Gmail API
│   ├── extractor.py                    # Extractores de datos (LLM y Mock determinista)
│   ├── exporters.py                    # Exportación a Excel, JSON y Google Sheets
│   └── pipeline.py                     # Pipeline integral de ingesta y validación
├── tests/                              # Suite de pruebas automatizadas (47 tests)
├── Dockerfile                          # Definición de construcción del contenedor Docker
├── docker-compose.yml                  # Configuración de servicios Docker Compose
├── pyproject.toml                      # Gestión de dependencias con Poetry
└── README.md                           # Documentación principal del proyecto
```

