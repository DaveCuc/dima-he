# Registro de Decisiones de Arquitectura (Architectural Decision Records - ADRs)

Este documento recopila las decisiones de diseño fundamentales tomadas durante el desarrollo del sistema **DIMA-HE**, su contexto, justificación técnica y consecuencias.

---

## ADR-001: Arquitectura Multiagente Distribuida de 7 Nodos A2A vs. Agente Monolítico

* **Estado:** Aceptado y Consolidado.
* **Contexto:**
  La evaluación heurística de interfaces web requiere explorar dinámicamente aplicaciones, capturar evidencias visuales/estructurales y analizar simultáneamente diez principios de usabilidad heterogéneos. Un único agente monolítico sufre de sobrecarga en la ventana de contexto de los LLMs, acoplamiento excesivo y falta de resiliencia ante fallos parciales.
* **Decisión:**
  Implementar una arquitectura distribuida de 7 microservicios desacoplados comunicados mediante el protocolo Agent2Agent (A2A HTTP JSON-RPC 2.0):
  * Nodo 0 (Orquestador).
  * Nodo 1 (Web Explorer).
  * Nodos 2 a 5 (Evaluadores especializados por dimensión: Diálogo, Acción, Estructura, Protección).
  * Nodo 6 (Generador de Reportes).
* **Consecuencias:**
  * ✅ Permite escalar y optimizar prompts y contextos especializados por dimensión heurística sin contaminar el resto del sistema.
  * ✅ Falla de un evaluador no detiene el ciclo de evaluación de los demás.
  * ⚠️ Requiere orquestación de red y contratos de datos estrictos (Pydantic v2).

---

## ADR-002: Delimitación Estricta de Protocolos: A2A Inter-Agente vs. MCP Agente-Herramienta

* **Estado:** Aceptado y Consolidado.
* **Contexto:**
  La proliferación de protocolos agénticos (A2A y MCP) genera ambigüedad sobre cuál usar para la colaboración entre agentes versus el control de herramientas.
* **Decisión:**
  * **Agent2Agent (A2A):** Utilizado **exclusivamente** para la comunicación horizontal y vertical entre los 7 nodos (descubrimiento vía `/.well-known/agent-card.json` y llamadas RPC tipadas).
  * **Model Context Protocol (MCP):** Utilizado **exclusivamente** como interfaz Agente-Herramienta entre el Nodo 1 (Web Explorer) y el contenedor de automatización Playwright MCP (`mcr.microsoft.com/playwright/mcp`).
* **Consecuencias:**
  * ✅ Ningún evaluador ni el orquestador interactúa directamente con el navegador, previniendo accesos concurrentes destructivos.
  * ✅ El explorador web es el único custodio del control de Chromium.

---

## ADR-003: Persistencia en Volumen Físico (`/app/evidence`) y Prohibición de Base64 en A2A

* **Estado:** Aceptado y Consolidado.
* **Contexto:**
  La transmisión de capturas de pantalla de alta resolución codificadas en Base64 en los payloads HTTP satura el ancho de banda de red, agota la memoria de los microservicios y causa desbordamiento de tokens en llamadas a modelos de lenguaje.
* **Decisión:**
  Prohibir terminantemente la inclusión de imágenes Base64 en las cargas útiles A2A. Toda evidencia visual (.png), árbol de accesibilidad (.json) y volcado DOM (.html) debe persistirse físicamente en el volumen `/app/evidence` y transmitirse únicamente como rutas relativas (`file_path`).
* **Consecuencias:**
  * ✅ Cargas útiles A2A ligeras y eficientes (pocos kilobytes).
  * ✅ Los evaluadores leen las capturas desde el disco directamente en modo solo lectura (`:ro`) e inyectan bytes al modelo vía `Part.from_bytes`.
  * ✅ Evidencia verificable y reproducible archivada físicamente para fines de auditoría científica.

---

## ADR-004: Patrones Deterministas Google ADK: EscalationChecker y DeduplicatorAgent en Python Puro

* **Estado:** Aceptado y Consolidado.
* **Contexto:**
  Delegar la validación de archivos en disco o la desduplicación de diagnósticos de usabilidad a un LLM introduce costos innecesarios, no-determinismo y latencias de inferencia.
* **Decisión:**
  * Implementar el agente validador `EvidenceValidatorAgent` como un `BaseAgent` de Google ADK en Python puro siguiendo el patrón **`EscalationChecker`**. Emite `EventActions(escalate=True)` únicamente si los tres archivos requeridos existen en disco y no están vacíos.
  * Implementar `DeduplicatorAgent` como un `BaseAgent` en Python puro que normaliza cadenas, agrupa hallazgos con base en clave compuesta `(página, heurística, selector)`, toma la severidad máxima y preserva los agentes e IDs de origen.
* **Consecuencias:**
  * ✅ Cero consumo de tokens en tareas deterministas.
  * ✅ Bucle de reintento (`LoopAgent(max_iterations=3)`) controlado matemáticamente.
  * ✅ Desduplicación rápida, reproducible y auditable.

---

## ADR-005: Sustitución de Reporte HTML por Reporte CSV para Análisis Estadístico Cuantitativo

* **Estado:** Aceptado y Consolidado.
* **Contexto:**
  El diseño original contemplaba `report.html` como salida principal. Sin embargo, para la redacción de la tesis y la evaluación comparativa, un archivo HTML es difícil de procesar programáticamente para generar gráficos o tablas estadísticas comparativas.
* **Decisión:**
  Sustituir `report.html` por **`report.csv`** (con formato estricto RFC 4180 y encomillado estándar `csv.QUOTE_ALL`) como el tercer elemento de la tríada oficial generada por el Nodo 6:
  1. `results.json`: Consumo programático integral.
  2. `report.md`: Tablas formateadas para inserción directa en el documento de tesis.
  3. `report.csv`: Análisis cuantitativo en hojas de cálculo y scripts estadísticos (Python/R).
* **Consecuencias:**
  * ✅ Facilita el cruce estadístico pre vs. post rediseño.
  * ✅ Reportes universales, ligeros y procesables sin motores de renderizado web.

---

## ADR-006: Motor de Evaluación Dual (Gemini Multimodal + Motor Determinista de Respaldo)

* **Estado:** Aceptado y Consolidado.
* **Contexto:**
  En entornos de integración continua (CI/CD) o auditorías locales sin credenciales de red, la dependencia obligatoria de una clave activa de Gemini API puede bloquear la ejecución de pruebas y despliegues.
* **Decisión:**
  Dotar a los 4 microservicios evaluadores de un motor de ejecución dual:
  1. Si `GOOGLE_API_KEY` está presente, realiza inferencia multimodal con Gemini API (`google-genai`).
  2. Si no hay conexión o falla la inferencia, activa automáticamente un motor de reglas determinista de respaldo que inspecciona patrones estructurales en el DOM y el árbol de accesibilidad.
* **Consecuencias:**
  * ✅ Cobertura y ejecución exitosa de pruebas al 100% en GitHub Actions CI sin requerir secretos de API.
  * ✅ Resiliencia operativa frente a desconexiones temporales del proveedor de nube.

---

## ADR-007: Profundidad de Rastreo Controlada (`max_depth = 1`) y Protección Anti-SSRF

* **Estado:** Aceptado y Consolidado.
* **Contexto:**
  Un explorador autónomo sin límites estrictos puede desencadenar rastreos infinitos, ciclos entre páginas o peticiones maliciosas hacia servicios internos de infraestructura (Server-Side Request Forgery).
* **Decisión:**
  * Fijar la profundidad de rastreo a un nivel máximo (`max_depth = 1`) partiendo de una lista base de URLs explícitas (`EvaluationScope`).
  * Aplicar un filtro de lista blanca anti-SSRF (`ALLOWED_TARGET_HOSTS`) en el Nodo 1 que rechaza cualquier navegación hacia IPs locales de metadatos o hosts no autorizados.
* **Consecuencias:**
  * ✅ Evaluaciones científicamente repetibles y predecibles en duración.
  * ✅ Seguridad de la red interna de contenedores y del entorno host.

---

## ADR-008: Postergación de Gemini Context Caching para Iteraciones Futuras

* **Estado:** Aceptado y Consolidado.
* **Contexto:**
  Gemini Context Caching permite ahorrar costos de tokens compartiendo contexto en solicitudes sucesivas. No obstante, en la versión v1.0 / v2.0, introducir Context Caching requiere un almacén centralizado de tokens de caché que acoplaría los 4 microservicios evaluadores independientes.
* **Decisión:**
  Mantener consultas independientes por cada evaluador y documentar el uso de Context Caching en la sección de trabajos futuros de la tesis.
* **Consecuencias:**
  * ✅ Máximo desacoplamiento y simplicidad arquitectónica entre los evaluadores.
  * ✅ Línea clara de optimización identificada para investigación posterior.
