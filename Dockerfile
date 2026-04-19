# Dockerfile para Railway
# Sirve la API FastAPI + archivos estaticos del dashboard
FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema para lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python
COPY requirements.txt requirements_api.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements_api.txt

# Instalar aiofiles explicitamente (requerido por FastAPI StaticFiles)
RUN pip install aiofiles>=23.2.1

# Copiar codigo
COPY . .

# Crear directorio de datos
RUN mkdir -p data

# Puerto expuesto (Railway lo asigna via $PORT)
EXPOSE 8000

# Comando de inicio
CMD ["python", "api_server.py"]
