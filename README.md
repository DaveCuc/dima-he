# Sistema Multiagente Distribuido para la Evaluación Heurística de Interfaces Web

Sistema multiagente distribuido para la evaluación heurística de interfaces web basado en las 10 heurísticas de usabilidad de Jakob Nielsen, implementado con Google Agent Development Kit (ADK), el protocolo Agent2Agent (A2A) y Microsoft Playwright MCP.

---

## Estructura del Proyecto

* **`orchestrator/`**: Nodo 0 (Orquestador). Coordina el ciclo de exploración, evaluadores paralelos, desduplicación de hallazgos y generación de reportes.
* **`web_explorer/`**: Nodo 1 (Web Explorer). Navegación e inspección mediante Playwright MCP, almacenamiento de evidencias físicas (capturas, snapshots de accesibilidad y DOM).
* **`evaluators/`**:
  * **`dialogue/`**: Nodo 2 (Heurísticas H1, H2, H10).
  * **`action/`**: Nodo 3 (Heurísticas H3, H7).
  * **`structure/`**: Nodo 4 (Heurísticas H4, H6, H8).
  * **`protection/`**: Nodo 5 (Heurísticas H5, H9).
* **`report_creator/`**: Nodo 6 (Report Creator). Síntesis y persistencia de reportes en formatos `json`, `md` y `csv`.
* **`shared/`**: Esquemas Pydantic v2, enumeraciones y utilidades de rutas compartidas.
* **`config/`**: Archivos de configuración YAML (`heuristics.yaml`, `agents.yaml`, `evaluation.yaml`).
* **`docs/`**: Documentación técnica (`architecture.md`, `deployment.md`, `decisions.md`).
* **`tests/`**: Suite de pruebas unitarias, de contrato A2A, de integración y E2E.

---

## Ejecución con Docker Compose

```bash
# Construir e iniciar todos los servicios
docker compose up -d --build

# Verificar estado de los contenedores
docker compose ps

# Detener los servicios
docker compose down
```

---

## Ejecución de Pruebas

```bash
# Ejecutar la suite completa de pruebas
pytest -v --tb=short
```

---

## Documentación Técnica

* [`docs/architecture.md`](docs/architecture.md): Arquitectura de nodos, protocolos y flujos de datos.
* [`docs/deployment.md`](docs/deployment.md): Guía de despliegue y variables de entorno.
* [`docs/decisions.md`](docs/decisions.md): Registro de decisiones de arquitectura (ADRs).
