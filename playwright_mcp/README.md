# Servicio de Infraestructura Playwright MCP

Este directorio documenta el contenedor de infraestructura Microsoft Playwright MCP (`mcr.microsoft.com/playwright/mcp:latest`).

## Especificación Operativa
* **Puerto interno en red Docker:** `8931` (Endpoint: `http://playwright-mcp:8931/mcp`)
* **Acceso desde el Host:** No expuesto (aislamiento de seguridad).
* **Consumo:** Exclusivo para el Nodo 1 (Web Explorer) mediante `McpToolset`.
* **Memoria Compartida:** `shm_size: "1gb"` en `docker-compose.yml` para evitar cierres de Chromium.
* **Red:** `extra_hosts: ["host.docker.internal:host-gateway"]` para acceder a la aplicación en el puerto `8000` del host.
