FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias del sistema requeridas
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar requerimientos de Python
COPY web_explorer/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copiar el paquete compartido y código fuente
COPY shared /app/shared
COPY config /app/config
COPY web_explorer /app/web_explorer

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8001

CMD ["uvicorn", "web_explorer.src.main:app", "--host", "0.0.0.0", "--port", "8001"]
