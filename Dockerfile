# ==============================================================================
# Dockerfile para RAG for Mails
# ==============================================================================
FROM python:3.12-slim-bookworm AS base

# Variables de entorno para Python y Poetry
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    POETRY_VERSION=1.8.3 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

# Instalar dependencias del sistema mínimas requeridas (curl para healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar Poetry
RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

# Directorio de trabajo
WORKDIR /app

# Copiar archivos de dependencias para aprovechar la caché de Docker
COPY pyproject.toml poetry.lock ./

# Instalar dependencias del proyecto (omitiendo dependencias dev)
RUN poetry install --without dev --no-root

# Copiar código fuente del proyecto
COPY src/ ./src/
COPY data/sample_mails/ ./data/sample_mails/
COPY main.py ./

# Crear directorio de datos de salida persistente
RUN mkdir -p /app/data/output

# Exponer el puerto de la API FastAPI
EXPOSE 8000

# Healthcheck para verificar disponibilidad del servicio
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Ejecutar el servidor Uvicorn en producción
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
