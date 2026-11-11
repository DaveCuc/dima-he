"""Pruebas de integración para el servicio Microsoft Playwright MCP (Fase 2)."""

import json
from pathlib import Path
import pytest
import httpx
from httpx_sse import connect_sse
from shared.utils.file_paths import ensure_evaluation_directories


MCP_BASE_URL = "http://localhost:8931"


class PlaywrightMcpClient:
    """Cliente mínimo SSE para interactuar con Playwright MCP en pruebas de integración."""

    def __init__(self, base_url: str = MCP_BASE_URL, timeout: float = 30.0):
        self.base_url = base_url
        self.timeout = timeout
        self.post_url: str | None = None
        self._msg_id = 0

    def _next_id(self) -> int:
        self._msg_id += 1
        return self._msg_id

    def execute_session(self, actions: list[dict]) -> list[dict]:
        """Ejecuta una secuencia de llamadas JSON-RPC sobre la conexión SSE y retorna las respuestas."""
        results = []
        with httpx.Client(timeout=self.timeout) as client:
            with connect_sse(client, "GET", f"{self.base_url}/sse") as event_source:
                for sse in event_source.iter_sse():
                    if sse.event == "endpoint":
                        self.post_url = f"{self.base_url}{sse.data}"
                        # 1. Enviar initialize
                        init_id = self._next_id()
                        client.post(
                            self.post_url,
                            json={
                                "jsonrpc": "2.0",
                                "id": init_id,
                                "method": "initialize",
                                "params": {
                                    "protocolVersion": "2024-11-05",
                                    "capabilities": {},
                                    "clientInfo": {"name": "test-client", "version": "1.0"},
                                },
                            },
                        )

                    elif sse.event == "message":
                        data = json.loads(sse.data)
                        msg_id = data.get("id")

                        # Ignorar notificaciones del servidor (mensajes sin id)
                        if msg_id is None:
                            continue

                        # Al responder initialize (id=1)
                        if msg_id == 1:
                            client.post(
                                self.post_url,
                                json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                            )
                            # Lanzar la primera acción
                            if actions:
                                act = actions.pop(0)
                                act["id"] = self._next_id()
                                client.post(self.post_url, json=act)
                        else:
                            # Guardar resultado de la acción completada
                            results.append(data)
                            if actions:
                                act = actions.pop(0)
                                act["id"] = self._next_id()
                                client.post(self.post_url, json=act)
                            else:
                                break
        return results


class TestPlaywrightMcpIntegration:
    """Valida los criterios de aceptación de la Fase 2 para Playwright MCP."""

    def test_mcp_service_connectivity_and_tools(self):
        client = PlaywrightMcpClient()
        actions = [
            {"jsonrpc": "2.0", "method": "tools/list", "params": {}},
        ]
        results = client.execute_session(actions)
        assert len(results) == 1
        assert "result" in results[0]
        tools = {t["name"] for t in results[0]["result"]["tools"]}

        # Verificar herramientas fundamentales requeridas por Blueprint v2.0
        expected_tools = {
            "browser_navigate",
            "browser_take_screenshot",
            "browser_snapshot",
            "browser_click",
            "browser_fill_form",
            "browser_evaluate",
            "browser_wait_for",
        }
        for tool in expected_tools:
            assert tool in tools, f"Herramienta requerida {tool} no expuesta por Playwright MCP"

    def test_navigation_and_screenshot_saved_to_evidence_volume(self):
        """Criterio de aceptación principal de Fase 2:
        Navegación y captura de prueba guardada físicamente en /app/evidence.
        """
        eval_id = "eval-phase2-test"
        # Asegurar directorio físico en el host
        host_evidence_base = Path("evidence")
        dirs = ensure_evaluation_directories(host_evidence_base, eval_id)
        target_screenshot_file = dirs["screenshots"] / "phase2_test.png"

        # Eliminar captura anterior si existiese
        if target_screenshot_file.exists():
            target_screenshot_file.unlink()

        # Ruta dentro del contenedor Docker
        container_screenshot_path = f"/app/evidence/evaluations/{eval_id}/exploration/screenshots/phase2_test.png"

        client = PlaywrightMcpClient(timeout=40.0)
        actions = [
            # 1. Navegar a página de prueba válida
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "browser_navigate",
                    "arguments": {
                        "url": "https://example.com",
                    },
                },
            },
            # 2. Tomar captura y guardarla en volumen
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "browser_take_screenshot",
                    "arguments": {
                        "scale": "css",
                        "filename": container_screenshot_path,
                        "fullPage": True,
                    },
                },
            },
            # 3. Extraer snapshot de accesibilidad
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "browser_snapshot",
                    "arguments": {},
                },
            },
        ]

        results = client.execute_session(actions)
        assert len(results) == 3

        # Verificar que la captura se persistió físicamente en el volumen del host
        assert target_screenshot_file.exists(), (
            f"La captura de pantalla no se guardó en el host en {target_screenshot_file.resolve()}"
        )
        assert target_screenshot_file.stat().st_size > 0, (
            "El archivo de captura de pantalla está vacío (0 bytes)."
        )

        # Verificar respuesta de snapshot de accesibilidad
        snapshot_res = results[2]["result"]
        assert "content" in snapshot_res
        snapshot_text = snapshot_res["content"][0]["text"]
        assert len(snapshot_text) > 0
        assert "Example Domain" in snapshot_text or "heading" in snapshot_text.lower()
