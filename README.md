# rag-for-mails 🏭

Sistema automatizado de extracción, validación estricta y sincronización de reportes operativos no estructurados enviados por correo o chat en plantas de moldeo por inyección.

Construido con **Python**, **LangChain**, **Ollama (`qwen3:8b`)**, **Pydantic V2** y **Rich**.

---

## 🎯 Entregables del Proyecto

1. 📄 [**Especificación del Prompt de Extracción (docs/PROMPT.md)**](docs/PROMPT.md)
   * Prompt exacto de sistema, Few-Shot guidance, esquema JSON formal y manejo de casos borde (unidades de tiempo, scrap, multi-máquina).
2. 📄 [**Documento de Arquitectura E2E y Prevención de Corrupción (docs/ARQUITECTURA_AUTOMATIZACION.md)**](docs/ARQUITECTURA_AUTOMATIZACION.md)
   * Stack técnico, pipeline de ingesta, capa de validación con Pydantic V2, Dead Letter Queue y persistencia en `output.json`.

---

## 🚀 Inicio Rápido

### 1. Instalación de Dependencias
```bash
poetry install
```

### 2. Ejecución de la Demostración (Caso del README)
Procesa el ejemplo estándar de moldeo (Turno 1, Máquina M102) y actualiza automáticamente los reportes:
```bash
poetry run python main.py demo
```

### 3. Procesamiento en Lote (Batch)
Procesa todos los correos de prueba en `data/sample_mails/` con visualización en tablas enriquecidas:
```bash
poetry run python main.py batch
```

### 4. Modo Interactivo
Permite elegir archivos o pegar texto de correos/chats directamente en la consola:
```bash
poetry run python main.py interactive
```

### 5. Procesar un Archivo Específico
```bash
poetry run python main.py process-file data/sample_mails/turno2_scrap_alto.txt
```

*(Nota: Si deseas forzar el extractor Mock determinista sin usar GPU/Ollama, puedes añadir la bandera `--mock` a cualquier comando).*

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
│   ├── config.py                      # Configuración de Ollama y rutas
│   ├── schemas.py                     # Modelos Pydantic V2 limpios
│   ├── extractor.py                   # Extractor LangChain + Ollama / Mock
│   ├── exporters.py                   # Exportador JSON limpio
│   └── pipeline.py                    # Orquestador del flujo E2E
├── main.py                            # CLI interactiva con Rich
├── pyproject.toml                     # Definición de dependencias Poetry
└── tests/
    └── test_all.py                    # Pruebas unitarias completas
```
