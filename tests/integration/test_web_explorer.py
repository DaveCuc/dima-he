"""Pruebas de integración para el Nodo 1 (Web Explorer) - Fase 3."""

import pytest
from pathlib import Path
from shared.schemas.evaluation import EvaluationRequest, EvaluationScope
from web_explorer.src.agent import create_web_explorer_agent, execute_web_exploration
from web_explorer.src.mcp_client import PlaywrightMcpClientAsync


class TestWebExplorerIntegration:
    """Valida los criterios de aceptación de Fase 3 para el Nodo 1 (Web Explorer)."""

    def test_create_web_explorer_adk_agent(self):
        """Verifica que el agente ADK se instancie con su McpToolset correspondiente."""
        agent = create_web_explorer_agent(
            mcp_sse_url="http://localhost:8931/sse"
        )
        assert agent.name == "web_explorer"
        assert len(agent.tools) == 1
        assert agent.disallow_transfer_to_parent is True
        assert agent.disallow_transfer_to_peers is True

    @pytest.mark.asyncio
    async def test_full_exploration_generates_all_three_evidences_on_disk(self):
        """Criterio de aceptación principal de Fase 3:
        Extracción de snapshot de accesibilidad, volcado DOM y captura física en disco.
        """
        eval_id = "eval-phase3-test"
        request = EvaluationRequest(
            evaluation_id=eval_id,
            target_url="https://example.com",
            scope=EvaluationScope(max_depth=0),
            instructions="Explorar la página principal y recopilar evidencia física completa.",
        )

        mcp_client = PlaywrightMcpClientAsync(base_url="http://localhost:8931/sse")
        result = await execute_web_exploration(
            request=request,
            base_evidence_dir="evidence",
            mcp_client=mcp_client,
        )

        assert result.evaluation_id == eval_id
        assert result.total_pages == 1
        assert len(result.pages_explored) == 1

        page = result.pages_explored[0]
        assert page.title == "Example Domain" or "Example" in page.title

        # 1. Verificar existencia física del Snapshot de Accesibilidad
        assert page.accessibility_snapshot_path is not None
        a11y_file = Path("evidence") / page.accessibility_snapshot_path
        assert a11y_file.exists(), f"Snapshot no existe en {a11y_file.resolve()}"
        assert a11y_file.stat().st_size > 0

        # 2. Verificar existencia física del Volcado DOM
        assert page.dom_reference_path is not None
        dom_file = Path("evidence") / page.dom_reference_path
        assert dom_file.exists(), f"DOM no existe en {dom_file.resolve()}"
        dom_content = dom_file.read_text(encoding="utf-8")
        assert "html" in dom_content.lower()
        assert "example" in dom_content.lower()

        # 3. Verificar existencia física de la Captura de Pantalla
        assert len(page.screenshots) >= 1
        screenshot_item = page.screenshots[0]
        scr_file = Path("evidence") / screenshot_item.file_path
        assert scr_file.exists(), f"Captura no existe en {scr_file.resolve()}"
        assert scr_file.stat().st_size > 0, "La captura de pantalla generada está vacía"
