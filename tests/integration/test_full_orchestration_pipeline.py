"""Pruebas de integración para la cadena completa de orquestación raíz (Fase 7).

Verifica el pipeline secuencial completo:
[exploration_loop -> parallel_evaluators -> deduplicator_agent -> remote_report_creator].
"""

import pytest
from pathlib import Path
from google.adk.events import Event, EventActions
from orchestrator.src.agent import execute_full_evaluation_pipeline, execute_orchestrated_evaluation
from orchestrator.src.remote_nodes import (
    RemoteEvaluatorAgent,
    RemoteReportCreatorAgent,
    RemoteWebExplorerAgent,
)
from report_creator.src.generator import ReportGenerator
from shared.schemas.evaluation import EvaluationRequest, EvaluationScope
from shared.schemas.finding import ConsolidatedFindings
from shared.utils.file_paths import ensure_evaluation_directories


class TestFullOrchestrationPipelineIntegration:
    """Valida la ejecución secuencial completa del root_agent."""

    @pytest.mark.asyncio
    async def test_full_pipeline_end_to_end_execution(self, tmp_path, monkeypatch):
        """Verifica que la ejecución completa de las 4 etapas genere hallazgos consolidados y reportes físicos."""
        temp_evidence = tmp_path / "evidence"
        eval_id = "eval-phase7-full"
        dirs = ensure_evaluation_directories(temp_evidence, eval_id)

        # 1. Crear evidencias físicas simuladas
        (dirs["screenshots"] / "page_01_home.png").write_bytes(b"\x89PNG\r\n\x1a\nfake-screenshot-data")
        (dirs["snapshots"] / "page_01_home.json").write_text('{"role": "WebArea", "name": "Reserva"}', encoding="utf-8")
        (dirs["dom"] / "page_01_home.html").write_text("<html><body>Reserva Tehuacán</body></html>", encoding="utf-8")

        # 2. Mockear RemoteWebExplorerAgent para simular exploración válida
        async def mock_explorer_run(self, ctx):
            exp_payload = {
                "evaluation_id": eval_id,
                "target_url": "https://example.com/reserva",
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

        # 3. Mockear RemoteEvaluatorAgent para simular hallazgos con duplicados intencionales
        async def mock_evaluator_run(self, ctx):
            dim = self.dimension
            # Diálogo y Acción reportan el mismo problema sobre el mismo selector (duplicado intencional)
            if dim in ["dialogue", "action"]:
                finding = {
                    "finding_id": f"find-{dim[:3]}-001",
                    "evaluation_id": eval_id,
                    "agent_id": f"evaluator_{dim}",
                    "problem": "Falta de indicador de carga en catálogo de especies",
                    "heuristic_id": "H1",
                    "heuristic_name": "Visibilidad del estado del sistema",
                    "justification": f"Justificación técnica proporcionada por evaluador de {dim}",
                    "location": {"page": "catalogo", "element": "GridContainer", "selector": "#species-grid"},
                    "evidence_ids": ["ev-scr-001"],
                    "severity": 2 if dim == "dialogue" else 3,
                    "severity_justification": "Impacta la retroalimentación inmediata del usuario.",
                    "improvement": "Añadir spinner o skeleton loader centrado.",
                    "confidence": 0.90,
                }
            elif dim == "structure":
                finding = {
                    "finding_id": "find-str-001",
                    "evaluation_id": eval_id,
                    "agent_id": "evaluator_structure",
                    "problem": "Tipografía heterogénea en títulos de fichas técnicas",
                    "heuristic_id": "H4",
                    "heuristic_name": "Consistencia y estándares",
                    "justification": "Los encabezados mezclan jerarquías visuales no estandarizadas.",
                    "location": {"page": "catalogo", "element": "CardTitle", "selector": ".card-title"},
                    "evidence_ids": ["ev-scr-002"],
                    "severity": 1,
                    "severity_justification": "Inconsistencia visual menor.",
                    "improvement": "Unificar con clase tipográfica global.",
                    "confidence": 0.85,
                }
            else:  # protection
                finding = {
                    "finding_id": "find-pro-001",
                    "evaluation_id": eval_id,
                    "agent_id": "evaluator_protection",
                    "problem": "Falta de confirmación previa a descarga de archivos volumétricos",
                    "heuristic_id": "H5",
                    "heuristic_name": "Prevención de errores",
                    "justification": "El botón descarga inmediatamente datasets pesados sin confirmación modal.",
                    "location": {"page": "descargas", "element": "DownloadButton", "selector": "#btn-download-zip"},
                    "evidence_ids": ["ev-scr-003"],
                    "severity": 2,
                    "severity_justification": "Puede generar consumo innecesario de datos móviles.",
                    "improvement": "Incorporar diálogo de confirmación indicando el peso del archivo.",
                    "confidence": 0.92,
                }

            yield Event(
                author=self.name,
                actions=EventActions(
                    escalate=False,
                    state_delta={f"findings_{dim}": [finding]},
                ),
            )

        monkeypatch.setattr(RemoteEvaluatorAgent, "_run_async_impl", mock_evaluator_run)

        # 4. Mockear RemoteReportCreatorAgent para generar físicamente los reportes usando ReportGenerator
        async def mock_report_creator_run(self, ctx):
            state = ctx.session.state if ctx.session else {}
            cons_data = state.get("consolidated_findings")
            consolidated = ConsolidatedFindings.model_validate(cons_data)

            generator = ReportGenerator(base_evidence_dir=temp_evidence)
            result = generator.generate_and_save_all(consolidated)

            yield Event(
                author=self.name,
                actions=EventActions(
                    escalate=False,
                    state_delta={
                        "report_files": result["files"],
                        "report_statistics": result["statistics"],
                    },
                ),
            )

        monkeypatch.setattr(RemoteReportCreatorAgent, "_run_async_impl", mock_report_creator_run)

        # 5. Ejecutar la cadena completa
        request = EvaluationRequest(
            evaluation_id=eval_id,
            target_url="https://example.com/reserva",
            scope=EvaluationScope(max_depth=0),
            instructions="Auditoría heurística completa de la plataforma Reserva Tehuacán-Cuicatlán.",
        )

        result = await execute_full_evaluation_pipeline(
            request=request,
            base_evidence_dir=temp_evidence,
            max_iterations=3,
        )

        # 6. Validaciones de la cadena secuencial
        assert result["evaluation_id"] == eval_id
        assert result["is_valid"] is True
        assert result["total_raw_findings"] == 4, "4 hallazgos brutos generados (2 en diálogo/acción, 1 estructura, 1 protección)"

        # Validar deduplicación
        assert result["total_consolidated_findings"] == 3, "Los dos duplicados de H1 deben consolidarse en 1 único hallazgo"
        assert result["duplicates_removed"] == 1

        # Validar generación física de reportes
        report_files = result["report_files"]
        assert "json" in report_files
        assert "markdown" in report_files
        assert "csv" in report_files

        reports_dir = temp_evidence / "evaluations" / eval_id / "reports"
        assert (reports_dir / "results.json").exists()
        assert (reports_dir / "report.md").exists()
        assert (reports_dir / "report.csv").exists()

        # Validar consistencia y contenido del Markdown
        md_content = (reports_dir / "report.md").read_text(encoding="utf-8")
        assert "Reporte de Evaluación Heurística de Usabilidad" in md_content
        assert "Falta de indicador de carga en catálogo de especies" in md_content
        assert "Severidad:** **3/4 (Mayor)" in md_content, "Debe preservar severidad máxima 3 para el hallazgo fusionado"

        # Validar que execute_orchestrated_evaluation con run_full_pipeline=True también funcione
        result_orch = await execute_orchestrated_evaluation(
            request=request,
            base_evidence_dir=temp_evidence,
            max_iterations=3,
            run_full_pipeline=True,
        )
        assert result_orch["total_consolidated_findings"] == 3
        assert result_orch["report_files"]["json"] == report_files["json"]
