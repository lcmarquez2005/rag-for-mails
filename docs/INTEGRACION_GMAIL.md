# Contexto de integración — Gmail

## Objetivo

Implementar únicamente la primera etapa del flujo de automatización: conexión con Gmail y filtrado de correos.

El sistema debe conectarse a una cuenta de Gmail mediante la API oficial de Google y recuperar exclusivamente los correos que cumplan con el remitente autorizado:

`l23200286@pachuca.tecnm.mx`

Los demás correos no deben ser procesados por el agente.

## Alcance

Esta integración debe cubrir solamente:

1. Autenticación con Gmail.
2. Conexión mediante Gmail API.
3. Consulta de mensajes recibidos.
4. Filtrado por remitente.
5. Recuperación del contenido de los correos que cumplan el filtro.
6. Entrega de esos correos al siguiente componente del sistema.

No implementar ni describir en esta etapa:

- LLM.
- Extracción de información.
- Pydantic.
- Google Sheets.
- Smartsheet.
- Excel.
- Validación del contenido generado.
- Reglas de negocio posteriores.

## Filtro requerido

El único remitente autorizado para procesamiento es:

`l23200286@pachuca.tecnm.mx`

La búsqueda en Gmail debe utilizar un filtro equivalente a:

`from:l23200286@pachuca.tecnm.mx`

Y con la caracteristica:

`is:unread`

para procesar únicamente mensajes no leídos y evitar reprocesamiento durante las pruebas.

## Flujo

```text
Gmail
  │
  ▼
Gmail API
  │
  ▼
Buscar mensajes
  │
  ▼
¿Remitente = l23200286@pachuca.tecnm.mx?
  │
  ├── NO → ignorar
  │
  └── SÍ
       │
       ▼
  Obtener contenido del correo
       │
       ▼
  Entregar correo al siguiente componente
```

## En Google Cloud Console:
Se genero un proyecto y se habilito la Gmail api y se descargo las credenciales del proeycto