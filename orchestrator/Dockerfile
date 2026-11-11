FROM python:3.12-slim

WORKDIR /app

# Instalar utilidades requeridas
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias de Python
COPY orchestrator/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copiar el paquete compartido y código fuente
COPY shared /app/shared
COPY config /app/config
COPY orchestrator /app/orchestrator

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "orchestrator.src.main:app", "--host", "0.0.0.0", "--port", "8000"]
