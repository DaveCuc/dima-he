"""Pruebas de integración para ParallelAgent y concurrencia de evaluadores (Fase 6)."""

import pytest
from pathlib import Path
from google.adk.events import Event, EventActions
from orchestrator.src.agent import execute_orchestrated_evaluation
from orchestrator.src.remote_nodes import RemoteEvaluatorAgent, RemoteWebExplorerAgent
from shared.schemas.evaluation import EvaluationRequest, EvaluationScope
from shared.utils.file_paths import ensure_evaluation_directories


class TestParallelEvaluatorsIntegration:
    """Valida la ejecución concurrente de los 4 evaluadores mediante ParallelAgent."""

    @pytest.mark.asyncio
    async def test_parallel_evaluators_concurrent_aggregation(self, tmp_path, monkeypatch):
        """Verifica que ParallelAgent dispare concurrentemente los 4 evaluadores y agregue sus hallazgos."""
        temp_evidence = tmp_path / "evidence"
        eval_id = "eval-phase6-parallel"
        dirs = ensure_evaluation_directories(temp_evidence, eval_id)

        # 1. Crear evidencias físicas simuladas
        (dirs["screenshots"] / "page_01_home.png").write_bytes(b"\x89PNG\r\n\x1a\nfake-screenshot")
        (dirs["snapshots"] / "page_01_home.json").write_text('{"role": "WebArea"}', encoding="utf-8")
        (dirs["dom"] / "page_01_home.html").write_text("<html><body>Simulado</body></html>", encoding="utf-8")

        # Mockear explorador web
        async def mock_explorer_run(self, ctx):
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
                    state_delta={"exploration_result": exp_payload},
                ),
            )

        monkeypatch.setattr(RemoteWebExplorerAgent, "_run_async_impl", mock_explorer_run)

        # Mockear evaluador remoto para simular respuestas concurrentes de cada dimensión
        async def mock_evaluator_run(self, ctx):
            dim = self.dimension
            simulated_finding = {
                "finding_id": f"find-{dim[:3]}-001",
                "evaluation_id": eval_id,
                "agent_id": f"node_{dim}",
                "problem": f"Problema simulado en dimensión {dim}",
                "heuristic_id": "H1" if dim == "dialogue" else ("H3" if dim == "action" else ("H4" if dim == "structure" else "H5")),
                "heuristic_name": "Heurística simulada",
                "justification": "Justificación de prueba",
                "location": {"page": "home", "element": "Elemento", "selector": "body"},
                "evidence_ids": [],
                "severity": 2,
                "severity_justification": "Severidad moderada",
                "improvement": "Recomendación accionable",
            }
            yield Event(
                author=self.name,
                actions=EventActions(
                    escalate=False,
                    state_delta={f"findings_{dim}": [simulated_finding]},
                ),
            )

        monkeypatch.setattr(RemoteEvaluatorAgent, "_run_async_impl", mock_evaluator_run)

        request = EvaluationRequest(
            evaluation_id=eval_id,
            target_url="https://example.com",
            scope=EvaluationScope(max_depth=0),
            instructions="Prueba de evaluadores paralelos Fase 6.",
        )

        result = await execute_orchestrated_evaluation(
            request=request,
            base_evidence_dir=temp_evidence,
            max_iterations=3,
        )

        assert result["evaluation_id"] == eval_id
        assert result["is_valid"] is True
        assert result["total_raw_findings"] == 4, "Debe agregar 1 hallazgo por cada una de las 4 dimensiones"

        findings_by_dim = result["findings_by_dimension"]
        assert len(findings_by_dim["dialogue"]) == 1
        assert len(findings_by_dim["action"]) == 1
        assert len(findings_by_dim["structure"]) == 1
        assert len(findings_by_dim["protection"]) == 1

        assert findings_by_dim["dialogue"][0]["finding_id"] == "find-dia-001"
        assert findings_by_dim["action"][0]["finding_id"] == "find-act-001"
        assert findings_by_dim["structure"][0]["finding_id"] == "find-str-001"
        assert findings_by_dim["protection"][0]["finding_id"] == "find-pro-001"
