"""Cliente MCP asíncrono para interactuar con el servidor Playwright MCP."""

import json
import logging
import os
from typing import Any, Dict, List, Optional
import httpx
from httpx_sse import aconnect_sse

logger = logging.getLogger(__name__)

DEFAULT_MCP_URL = os.getenv("PLAYWRIGHT_MCP_URL", "http://playwright-mcp:8931/sse")


class PlaywrightMcpClientAsync:
    """Cliente asíncrono sobre transporte SSE para invocar herramientas de Playwright MCP."""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 60.0):
        url = base_url or DEFAULT_MCP_URL
        # Si la URL termina en /mcp, ajustar al endpoint SSE
        if url.endswith("/mcp"):
            url = url[:-4] + "/sse"
        elif not url.endswith("/sse"):
            url = url.rstrip("/") + "/sse"
        self.sse_url = url
        self.base_url = url.rsplit("/sse", 1)[0]
        self.timeout = timeout
        self.post_url: Optional[str] = None
        self._msg_id = 0

    def _next_id(self) -> int:
        self._msg_id += 1
        return self._msg_id

    async def call_tools_pipeline(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Abre una sesión SSE con Playwright MCP, ejecuta la lista de llamadas a herramientas y retorna sus resultados.
        
        Args:
            tool_calls: Lista de diccionarios con formato:
                {"name": "browser_navigate", "arguments": {"url": "..."}}
        """
        results: List[Dict[str, Any]] = []
        pending_calls = list(tool_calls)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with aconnect_sse(client, "GET", self.sse_url) as event_source:
                async for sse in event_source.aiter_sse():
                    if sse.event == "endpoint":
                        self.post_url = f"{self.base_url}{sse.data}"
                        # 1. Enviar initialize
                        init_id = self._next_id()
                        await client.post(
                            self.post_url,
                            json={
                                "jsonrpc": "2.0",
                                "id": init_id,
                                "method": "initialize",
                                "params": {
                                    "protocolVersion": "2024-11-05",
                                    "capabilities": {},
                                    "clientInfo": {"name": "web-explorer-agent", "version": "2.0"},
                                },
                            },
                        )

                    elif sse.event == "message":
                        data = json.loads(sse.data)
                        msg_id = data.get("id")

                        # Ignorar notificaciones broadcast (mensajes sin id)
                        if msg_id is None:
                            continue

                        # Respuesta al handshake initialize
                        if msg_id == 1:
                            await client.post(
                                self.post_url,
                                json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                            )
                            # Lanzar la primera herramienta
                            if pending_calls:
                                call = pending_calls.pop(0)
                                req_id = self._next_id()
                                await client.post(
                                    self.post_url,
                                    json={
                                        "jsonrpc": "2.0",
                                        "id": req_id,
                                        "method": "tools/call",
                                        "params": {
                                            "name": call["name"],
                                            "arguments": call.get("arguments", {}),
                                        },
                                    },
                                )
                        else:
                            # Respuesta a una herramienta
                            results.append(data.get("result", {}))
                            if pending_calls:
                                call = pending_calls.pop(0)
                                req_id = self._next_id()
                                await client.post(
                                    self.post_url,
                                    json={
                                        "jsonrpc": "2.0",
                                        "id": req_id,
                                        "method": "tools/call",
                                        "params": {
                                            "name": call["name"],
                                            "arguments": call.get("arguments", {}),
                                        },
                                    },
                                )
                            else:
                                # Todas las herramientas ejecutadas
                                break

        return results

    async def navigate(self, url: str) -> Dict[str, Any]:
        """Navega a una URL específica."""
        results = await self.call_tools_pipeline([{"name": "browser_navigate", "arguments": {"url": url}}])
        return results[0] if results else {}

    async def take_screenshot(
        self,
        filename: str,
        full_page: bool = True,
        scale: str = "css",
    ) -> Dict[str, Any]:
        """Toma una captura de pantalla guardándola en filename."""
        results = await self.call_tools_pipeline([
            {
                "name": "browser_take_screenshot",
                "arguments": {
                    "filename": filename,
                    "fullPage": full_page,
                    "scale": scale,
                },
            }
        ])
        return results[0] if results else {}

    async def get_snapshot(self) -> str:
        """Extrae el árbol de accesibilidad de la página actual."""
        results = await self.call_tools_pipeline([{"name": "browser_snapshot", "arguments": {}}])
        if results and "content" in results[0]:
            content = results[0]["content"]
            if isinstance(content, list) and content:
                return content[0].get("text", "")
        return ""

    async def evaluate_js(self, expression: str) -> Any:
        """Evalúa una expresión JavaScript en el contexto del DOM."""
        results = await self.call_tools_pipeline([
            {"name": "browser_evaluate", "arguments": {"expression": expression}}
        ])
        if results and "content" in results[0]:
            content = results[0]["content"]
            if isinstance(content, list) and content:
                return content[0].get("text", "")
        return ""
