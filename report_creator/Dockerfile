FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY report_creator/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY shared /app/shared
COPY config /app/config
COPY report_creator /app/report_creator

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8006

CMD ["uvicorn", "report_creator.src.main:app", "--host", "0.0.0.0", "--port", "8006"]
