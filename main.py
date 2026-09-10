import uvicorn
from src.config import API_HOST, API_PORT
from src.api.app import app  # Exportar app para uvicorn src.main:app o main:app

def main():
    print(f"🚀 Iniciando RAG for Mails API en http://{API_HOST}:{API_PORT}")
    print(f"📖 Documentación Swagger UI disponible en: http://127.0.0.1:{API_PORT}/docs")
    uvicorn.run("src.api.app:app", host=API_HOST, port=API_PORT, reload=True)


if __name__ == "__main__":
    main()
