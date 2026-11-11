"""Definición del Agente Web Explorer (Nodo 1) con Google ADK y Gemini API."""

import os
from typing import Optional
from google.adk.agents import Agent
from google.adk.tools import McpToolset
from google.adk.tools.mcp_tool.mcp_toolset import SseConnectionParams

from shared.schemas.evaluation import EvaluationRequest
from shared.schemas.exploration import ExplorationResult
from web_explorer.src.explorer import SafeWebExplorer
from web_explorer.src.mcp_client import PlaywrightMcpClientAsync

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
DEFAULT_MCP_URL = os.getenv("PLAYWRIGHT_MCP_URL", "http://playwright-mcp:8931/sse")


def create_web_explorer_agent(
    model: str = DEFAULT_MODEL,
    mcp_sse_url: str = DEFAULT_MCP_URL,
) -> Agent:
    """Crea la instancia de Google ADK Agent configurada con McpToolset para navegación."""
    # Configurar herramientas MCP sobre SSE
    playwright_toolset = McpToolset(
        connection_params=SseConnectionParams(url=mcp_sse_url)
    )

    agent = Agent(
        name="web_explorer",
        description="Agente especializado en exploración multimodal y extracción de evidencia física de interfaces web.",
        model=model,
        instruction="""Eres el Agente Web Explorer del sistema de evaluación heurística.
Tu responsabilidad exclusiva es navegar la plataforma web objetivo, recopilar capturas de pantalla,
árboles de accesibilidad y volcados del DOM sin ejecutar acciones destructivas ni alterar la base de datos.
- Sigue fielmente el alcance de páginas y rutas solicitadas.
- Asegúrate de esperar a que los componentes dinámicos terminen de cargar antes de tomar capturas.
- No realices pagos, compras, modificaciones ni borrados de registros.
""",
        tools=[playwright_toolset],
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )
    return agent


async def execute_web_exploration(
    request: EvaluationRequest,
    base_evidence_dir: str = "evidence",
    mcp_client: Optional[PlaywrightMcpClientAsync] = None,
) -> ExplorationResult:
    """Ejecuta el flujo completo de exploración y persistencia de evidencias físicas."""
    explorer = SafeWebExplorer(
        mcp_client=mcp_client,
        base_evidence_dir=base_evidence_dir,
    )
    return await explorer.explore(request)
