# Guía de Despliegue y Operación (Deployment Guide)

Este documento detalla los requerimientos, la configuración de variables de entorno y los pasos operativos para desplegar el sistema distribuido **DIMA-HE** mediante Docker Compose o en el entorno anfitrión local.

---

## 1. Requisitos del Sistema

### 1.1. Despliegue en Contenedores (Recomendado)
* **Docker:** Versión 24.0+ (Verificado con Docker 29.9.3 en Windows 11 y Linux).
* **Docker Compose:** Versión v2.20+ (Verificado con v5.7.0).
* **Memoria RAM:** Mínimo 4 GB disponibles (Chromium headless requiere al menos 1 GB de memoria compartida `shm_size: 1gb`).
* **Almacenamiento:** Mínimo 2 GB de espacio libre para imágenes Docker y volumen de evidencias.

### 1.2. Entorno Local de Desarrollo (Host)
* **Python:** Versión 3.12+ (con dependencias de `requirements.txt` o `pyproject.toml`).
* **Node.js / Chromium:** Para el servicio de infraestructura Playwright MCP si se ejecuta fuera de Docker.

---

## 2. Configuración de Variables de Entorno (`.env`)

Crea un archivo `.env` en la raíz del proyecto basándote en `.env.example`:

```bash
cp .env.example .env
```

### Tabla de Variables de Entorno

| Variable | Descripción | Valor por Defecto | Ámbito |
| :--- | :--- | :--- | :--- |
| `GOOGLE_API_KEY` | Clave de API de Gemini para inferencia multimodal (Nodos 1 a 5). | *(Opcional en CI / modo determinista)* | Global |
| `GEMINI_MODEL` | Modelo de Gemini utilizado por los evaluadores y explorador. | `gemini-2.5-flash` | Global |
| `ORCHESTRATOR_HOST_PORT` | Puerto expuesto en el host para el Orquestador (evita conflictos con :8000). | `8010` | Nodo 0 |
| `PLAYWRIGHT_MCP_URL` | URL de conexión al servicio de infraestructura Playwright MCP. | `http://playwright-mcp:8931/` | Nodo 1 |
| `ALLOWED_TARGET_HOSTS` | Lista blanca de dominios y hosts permitidos para protección anti-SSRF. | `host.docker.internal:8000,localhost:8000,example.com` | Nodo 1 |
| `EVIDENCE_DIR` | Ruta del volumen de evidencias dentro del contenedor. | `/app/evidence` | Todos los Nodos |

---

## 3. Despliegue con Docker Compose

### 3.1. Construcción y Arranque de la Red de Servicios

Ejecuta el siguiente comando para construir las imágenes y levantar los 8 contenedores en segundo plano:

```bash
docker compose up -d --build
```

### 3.2. Verificación de Salud de los Servicios

Todos los servicios cuentan con `healthcheck` integrado. Puedes consultar el estado operativo con:

```bash
docker compose ps
```

La salida esperada confirmará el estado `healthy` en los 8 contenedores:
```plaintext
NAME                   IMAGE                                        STATUS
orchestrator           herramienta-tesis-orchestrator               Up (healthy)
web-explorer           herramienta-tesis-web-explorer               Up (healthy)
evaluator-dialogue     herramienta-tesis-evaluator-dialogue         Up (healthy)
evaluator-action       herramienta-tesis-evaluator-action           Up (healthy)
evaluator-structure    herramienta-tesis-evaluator-structure        Up (healthy)
evaluator-protection   herramienta-tesis-evaluator-protection       Up (healthy)
report-creator         herramienta-tesis-report-creator             Up (healthy)
playwright-mcp         mcr.microsoft.com/playwright/mcp:latest      Up (healthy)
```

### 3.3. Comprobación Directa de Endpoints de Salud

```bash
# Nodo 0: Orquestador
curl -s http://localhost:8010/health

# Nodo 1: Web Explorer
curl -s http://localhost:8001/health

# Nodos 2 al 5: Evaluadores Heurísticos
curl -s http://localhost:8002/health
curl -s http://localhost:8003/health
curl -s http://localhost:8004/health
curl -s http://localhost:8005/health

# Nodo 6: Report Creator
curl -s http://localhost:8006/health
```

---

## 4. Ejecución de una Auditoría Heurística

### 4.1. Vía Endpoint REST Directo (`POST /evaluate`)

Envía un payload `EvaluationRequest` al Orquestador (Host port `8010`):

```bash
curl -X POST http://localhost:8010/evaluate?full_pipeline=true \
  -H "Content-Type: application/json" \
  -d '{
    "evaluation_id": "eval-tehuacan-001",
    "target_url": "http://host.docker.internal:8000",
    "scope": {
      "max_depth": 1,
      "base_urls": ["http://host.docker.internal:8000"]
    },
    "instructions": "Auditar flujo turístico y catálogo de especies de la Reserva de la Biosfera."
  }'
```

### 4.2. Vía Protocolo Estándar A2A (`POST /a2a/v1/message`)

```bash
curl -X POST http://localhost:8010/a2a/v1/message \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "audit-req-001",
    "method": "message/send",
    "params": {
      "full_pipeline": true,
      "message": {
        "parts": [
          {
            "data": {
              "evaluation_id": "eval-tehuacan-001",
              "target_url": "http://host.docker.internal:8000",
              "scope": {"max_depth": 1},
              "instructions": "Auditoría completa de usabilidad."
            }
          }
        ]
      }
    }
  }'
```

---

## 5. Inspección de Evidencias y Reportes Generados

Tras la ejecución, las evidencias físicas y reportes quedarán almacenados en la carpeta montada `./evidence/evaluations/{evaluation_id}/`:

```plaintext
evidence/evaluations/eval-tehuacan-001/
├── exploration/
│   ├── screenshots/
│   │   └── page_01_home.png        <- Captura física de alta resolución
│   ├── snapshots/
│   │   └── page_01_home_a11y.json  <- Árbol de accesibilidad semántico
│   └── dom/
│       └── page_01_home_dom.html   <- Volcado estructurado del DOM
├── findings/
│   └── consolidated_findings.json  <- Hallazgos desduplicados determinísticamente
└── reports/
    ├── results.json                <- Datos estructurados para consumo programático
    ├── report.md                   <- Tablas y diagnósticos formateados para tesis
    └── report.csv                  <- Datos tabulares para análisis estadístico (RFC 4180)
```

---

## 6. Monitoreo y Diagnóstico

### Logs en Vivo
Para inspeccionar la actividad de los microservicios en tiempo real:
```bash
# Ver logs de toda la red
docker compose logs -f

# Ver logs de un nodo específico (ej. Orquestador o Explorador)
docker compose logs -f orchestrator
docker compose logs -f web-explorer
```

### Detención y Limpieza
```bash
# Detener contenedores preservando evidencias
docker compose down

# Detener y reiniciar limpiando contenedores
docker compose down -v
```
