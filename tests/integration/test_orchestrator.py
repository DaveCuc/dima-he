"""Pruebas de integración para el Nodo 0 (Orquestador) - Fase 5."""

import pytest
from fastapi.testclient import TestClient
from orchestrator.src.main import app
from orchestrator.src.agent import execute_orchestrated_exploration
from shared.schemas.evaluation import EvaluationRequest, EvaluationScope
from shared.utils.file_paths import ensure_evaluation_directories

client = TestClient(app)


class TestOrchestratorIntegration:
    """Valida los criterios de aceptación de Fase 5 para el Orquestador."""

    def test_orchestrator_health_endpoint(self):
        """Verifica que el orquestador responda a su healthcheck."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["node_id"] == "node_0_orchestrator"

    def test_orchestrator_agent_card_discovery(self):
        """Criterio de aceptación A2A para el Orquestador:
        GET /.well-known/agent-card.json debe exponer la tarjeta del orquestador.
        """
        response = client.get("/.well-known/agent-card.json")
        assert response.status_code == 200
        card = response.json()
        assert card["name"] == "orchestrator"
        assert card["protocol_binding"] == "JSONRPC"
        assert "skills" in card
        assert len(card["skills"]) >= 1
        skill = card["skills"][0]
        assert skill["id"] == "evaluate_interface"
        assert "EvaluationRequest" in skill["input_schema"]["title"]

    def test_orchestrator_rpc_invalid_request(self):
        """Verifica que peticiones RPC sin id o método sean rechazadas."""
        response = client.post("/", json={"foo": "bar"})
        assert response.status_code == 400
        data = response.json()
        assert data["error"]["code"] == -32600

    @pytest.mark.asyncio
    async def test_full_orchestrated_loop_with_validator_escalation(self, tmp_path, monkeypatch):
        """Verifica la ejecución orquestada completa del LoopAgent:
        El explorador remoto mockeado genera evidencias físicas y el EvidenceValidatorAgent
        las detecta, emitiendo EventActions(escalate=True) para concluir el bucle.
        """
        temp_evidence = tmp_path / "evidence"
        eval_id = "eval-phase5-loop"
        dirs = ensure_evaluation_directories(temp_evidence, eval_id)

        # Mockear RemoteWebExplorerAgent para simular la persistencia física del Nodo 1
        from orchestrator.src.remote_nodes import RemoteWebExplorerAgent
        from google.adk.events import Event, EventActions

        async def mock_run_async_impl(self, ctx):
            # Simular generación física de evidencias en el volumen
            (dirs["screenshots"] / "page_01_home.png").write_bytes(b"\x89PNG\r\n\x1a\nsimulated-screenshot")
            (dirs["snapshots"] / "page_01_home.json").write_text('{"role": "WebArea"}', encoding="utf-8")
            (dirs["dom"] / "page_01_home.html").write_text("<html>Simulado</html>", encoding="utf-8")

            exp_payload = {
                "evaluation_id": eval_id,
                "target_url": "https://example.com",
                "total_pages": 1,
                "pages_explored": [],
            }
            yield Event(
                author=self.name,
                actions=EventActions(
                    escalate=False,
                    state_delta={
                        "exploration_result": exp_payload,
                    },
                ),
            )

        monkeypatch.setattr(RemoteWebExplorerAgent, "_run_async_impl", mock_run_async_impl)

        request = EvaluationRequest(
            evaluation_id=eval_id,
            target_url="https://example.com",
            scope=EvaluationScope(max_depth=0),
            instructions="Prueba de orquestación Fase 5 con LoopAgent y EscalationChecker.",
        )

        result = await execute_orchestrated_exploration(
            request=request,
            base_evidence_dir=temp_evidence,
            max_iterations=3,
        )

        assert result["evaluation_id"] == eval_id
        assert result["is_valid"] is True
        assert "Evidencias físicas verificadas" in result["validation_details"]
        assert result["exploration_result"] is not None
