# AGENTS.md - Contexto Estático Global del Proyecto

Este documento constituye la **única fuente de contexto permanente, reglas operativas, patrones de diseño y decisiones arquitectónicas** para cualquier agente autónomo o desarrollador que opere en este repositorio.

Toda especificación técnica detallada de componentes, contratos de datos y fases de desarrollo se rige por:
👉 **[`blueprint.md`](file:///c:/Users/DaveCuc/Projects/herramienta-tesis/blueprint.md)**

---

## 1. Propósito e Identidad del Sistema

* **Identidad del Agente:** Arquitecto de Software Agéntico y Desarrollador Full-Stack especializado en sistemas multiagente distribuidos, protocolos abiertos de comunicación e inferencia multimodal.
* **Propósito del Sistema:** Implementar un **Sistema Multiagente Distribuido para la Evaluación Heurística de Interfaces Web** basado en las 10 heurísticas de usabilidad de Jakob Nielsen, orientado inicialmente al caso de uso de auditoría de la plataforma web de la Reserva de la Biosfera Tehuacán-Cuicatlán.
* **Alcance General:** Explorar de forma determinista y segura una interfaz web, recopilar evidencia visual y estructural física (capturas de pantalla, árbol de accesibilidad, DOM y registros de interacción), evaluar hallazgos en cuatro dimensiones funcionales paralelas (Diálogo, Acción, Estructura, Protección), desduplicar resultados determinísticamente y consolidar reportes en formatos `json`, `md` y `csv`.

---

## 2. Pila Tecnológica y Convenciones

### 2.1. Tecnologías Detectadas y Declaradas
* **Entorno Anfitrión (Host):** Windows 11 con Python 3.12.10 local (`C:\Users\DaveCuc\AppData\Local\Programs\Python\Python312\python.exe`) y Node.js v25.6.1 / npx 11.9.0.
* **Entorno de Despliegue en Contenedores:** Docker 29.9.3 y Docker Compose v5.7.0 (contenedores base Linux `python:3.11-slim` o `python:3.12-slim`).
* **Framework de Agentes:** Google Agent Development Kit (`google-adk`).
* **Protocolos de Comunicación:**
  * **Agent2Agent (A2A):** Protocolo de comunicación HTTP/JSON entre los 7 nodos (`/.well-known/agent-card.json`).
  * **Model Context Protocol (MCP):** Exclusivo para la conexión entre el Nodo 1 (Web Explorer) y el contenedor de automatización `mcr.microsoft.com/playwright/mcp:8931`.
* **Motor de Automatización de Navegador:** Microsoft Playwright MCP sobre Chromium Headless.
* **Proveedor LLM / Multimodal:** Gemini API mediante SDK oficial `google-genai`.
* **Validación de Datos y Contratos:** Pydantic v2 para esquemas estrictos de entrada y salida (`output_schema`).
* **Capa Web de Microservicios:** FastAPI + Uvicorn + HTTPX asíncrono.
* **Harness de Habilidades Instaladas:** Ubicadas en [`.agents/skills/`](file:///c:/Users/DaveCuc/Projects/herramienta-tesis/.agents/skills/):
  * `adk-agent-builder`: Orquestación multiagente en Google ADK.
  * `adk-a2a-developer`: Implementación de endpoints y agentes A2A.
  * `mcp-builder`: Integración del cliente MCP.
  * `playwright-explore-website`: Automatización de navegación e inspección DOM.
  * `gemini-api-dev`: Inferencia multimodal con `google-genai`.

### 2.2. Patrones Arquitectónicos de Google ADK (Inspiración Google Codelab)
Basado en *Production-Ready AI Roadshow: Building a Multi-Agent System*:
1. **LoopAgent determinista:** Empleado en el Nodo 0 (`exploration_loop`) para ejecutar el ciclo de extracción de evidencia con `max_iterations=3`. Sub-agentes: `[remote_web_explorer, evidence_validator_agent]`.
2. **EscalationChecker con BaseAgent (Python puro):** Implementado en `EvidenceValidatorAgent`. Inspecciona físicamente en `/app/evidence` la existencia y validez de capturas y snapshots.
   * Evidencia válida: emite `Event(author=self.name, actions=EventActions(escalate=True))` para romper el bucle.
   * Evidencia incompleta: escribe motivo en `ctx.session.state["exploration_feedback"]` y reintenta.
3. **SequentialAgent como columna vertebral:** Concatena `[exploration_loop, parallel_evaluators, deduplicator_agent, remote_report_creator]`.
4. **ParallelAgent para evaluadores concurrentes:** Dispara en paralelo las invocaciones A2A a los 4 nodos evaluadores (Diálogo, Acción, Estructura, Protección).
5. **DeduplicatorAgent determinista:** BaseAgent en Python puro que agrupa y desduplica hallazgos sin realizar llamadas innecesarias a LLMs.

### 2.3. Delimitación Estricta de Protocolos
| Protocolo | Ámbito de Aplicación | Componentes Involucrados |
| :--- | :--- | :--- |
| **Agent2Agent (A2A)** | Comunicación Inter-Agente | Toda interacción entre los **7 Nodos** (N0 a N6). Descubrimiento vía `/.well-known/agent-card.json` y llamadas HTTP con payloads Pydantic v2. |
| **Model Context Protocol (MCP)** | Conexión Agente-Herramienta | **Exclusivamente** entre el **Nodo 1 (Web Explorer)** y el contenedor `mcr.microsoft.com/playwright/mcp:8931` mediante `McpToolset`. |

### 2.4. Convenciones de Código y Entorno Host
* **Tipado Estricto:** Todo código Python debe contar con type annotations completas y validación de tipos con Pydantic v2 en `shared/schemas/`.
* **Portabilidad de Rutas:** Uso obligatorio de `pathlib.Path` para evitar errores entre rutas Windows (`\`) y Linux (`/`).
* **Aislamiento de Dependencias:** Cada nodo contará con su propio `requirements.txt` y `Dockerfile` dentro de su directorio correspondiente.
* **Documentación y Mantenibilidad:** Preservar docstrings y comentarios existentes. Formato de saltos de línea `LF` en archivos destinados a contenedores Docker.
* **Estructura Modular de Evaluadores:** Los evaluadores residen en carpetas independientes (`evaluators/dialogue`, `action`, `structure`, `protection`) para desacoplar sus futuros contextos y heurísticas.
* **Resolución del Web App local:** `http://host.docker.internal:8000` (el servidor Laravel o web de prueba en el host debe bindearse a `0.0.0.0:8000`).
* **Memoria de Chromium:** `shm_size: "1gb"` en el servicio `playwright-mcp`.

---

## 3. Reglas Operativas Duras (Guardrails Estáticos)

1. **Inviolabilidad de la Especificación:** No alterar la arquitectura de 7 nodos A2A + 1 servicio de infraestructura Playwright MCP definida en `blueprint.md`.
2. **Prohibición de Base64 en A2A:** No transmitir imágenes codificadas en Base64 en las cargas útiles de los mensajes A2A. Toda evidencia visual o estructural debe persistirse físicamente en el volumen `/app/evidence` y transmitirse como rutas relativas (`file_path`).
3. **No Invención de Tecnologías / Bases de Datos:** No introducir bases de datos externas (PostgreSQL, MongoDB, MySQL), brokers de colas (Redis, RabbitMQ, Kafka) ni plataformas de orquestación complejas (Kubernetes). La persistencia de evidencias y estado se realiza en archivos y en memoria de sesión controlada.
4. **Protección Anti-SSRF:** Prohibido realizar peticiones HTTP o navegación hacia IPs de infraestructura de red interna o metadatos en la nube (`169.254.x.x`, `172.x.x.x`), permitiendo únicamente los dominios explícitos configurados en `ALLOWED_TARGET_HOSTS` (ej. `host.docker.internal:8000`).
5. **No Acciones Destructivas:** La exploración web del Nodo 1 debe limitarse a navegación, lectura de componentes, inspección de formularios y clics seguros; queda prohibido ejecutar pagos, borrados o acciones que alteren la base de datos de la aplicación auditada.
6. **Gestión Segura de Secretos:** Prohibido almacenar claves de API (`GOOGLE_API_KEY`) o credenciales en texto plano en el código o en repositorios Git. Toda variable sensible debe consumirse desde variables de entorno (`.env`).
7. **Disciplina de Fases:** No iniciar la codificación de una fase subsecuente sin la aprobación explícita del usuario y la verificación de criterios de aceptación de la fase actual.

---

## 4. Decisiones de Diseño Consolidadas (Validadas por el Arquitecto)

1. **Estrategia de Autenticación en la Web Objetivo:**
   * La evaluación inicial de la plataforma de la Reserva (`reserva-platform`) se centrará principalmente en rutas públicas de información, catálogos y módulos de consulta turística.
   * Para flujos privados, se contempla un paso de autenticación inicial parametrizado mediante credenciales de prueba inyectadas por el Nodo 1 al inicio de la sesión.
2. **Límites de Espera (Timeouts de Navegación):**
   * Carga inicial de página: máximo **30 segundos**.
   * Interacciones complejas (apertura de modales, despliegue de menús, componentes dinámicos de Inertia.js): máximo **60 segundos**.
3. **Estrategia de Inferencia Gemini (Sin Context Caching en v1.0):**
   * Consultas independientes sin Context Caching para mantener la simplicidad y el desacoplamiento limpio entre los 4 microservicios evaluadores A2A.
   * El uso de Context Caching de Gemini API queda formalmente registrado como trabajo futuro para optimización de costos en iteraciones posteriores.
4. **Profundidad de Rastreo (Crawl Depth Híbrido):**
   * El esquema `EvaluationScope` definirá una lista base de URLs obligatorias para garantizar la repetibilidad científica de la evaluación.
   * Se otorga autonomía de exploración limitada a un nivel de profundidad máximo (`max_depth = 1`) para descubrir enlaces hijos directos relacionados con el flujo bajo prueba.
5. **Formatos Oficiales de Reporte (Nodo 6):**
   * Se sustituye `report.html` por **`report.csv`** para facilitar el análisis estadístico en hojas de cálculo y herramientas analíticas.
   * Salidas oficiales persistidas en `/app/evidence/evaluations/{evaluation_id}/reports/`:
     * `results.json`: Datos estructurados completos para consumo programático.
     * `report.md`: Resumen ejecutivo y tablas formateadas para inserción directa en el documento de tesis.
     * `report.csv`: Datos tabulares limpios para análisis estadístico cuantitativo.
