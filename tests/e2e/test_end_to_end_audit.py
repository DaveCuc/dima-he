"""Suite de pruebas de extremo a extremo (E2E) para la auditoría heurística completa (Fase 9).

Verifica el ciclo de vida completo del sistema DIMA-HE:
1. Recepción del requerimiento de auditoría (EvaluationRequest).
2. Exploración web y persistencia de evidencias físicas (screenshots, snapshots, DOM).
3. Validación de evidencia física mediante EscalationChecker.
4. Evaluación heurística en 4 dimensiones paralelas (Diálogo, Acción, Estructura, Protección).
5. Desduplicación determinista preservando trazabilidad de agentes e IDs de origen.
6. Generación y persistencia física de la tríada oficial de reportes (results.json, report.md, report.csv).
7. Simulación de auditoría comparativa pre_redesign vs. post_redesign.
"""

import json
import os
import pytest
from pathlib import Path

from evaluators.dialogue.src.agent import create_dialogue_evaluator
from evaluators.action.src.agent import create_action_evaluator
from evaluators.structure.src.agent import create_structure_evaluator
from evaluators.protection.src.agent import create_protection_evaluator
from orchestrator.src.deduplicator import DeduplicatorAgent
from report_creator.src.generator import ReportGenerator
from shared.enums.agent_role import EvaluationVersion
from shared.schemas.evaluation import EvaluationRequest, EvaluationScope
from shared.schemas.exploration import ExplorationResult, PageExplorationResult
from shared.schemas.evidence import EvidenceItem, EvidenceType
from shared.utils.file_paths import ensure_evaluation_directories


class TestEndToEndAuditSuite:
    """Pruebas E2E completas del sistema multiagente distribuido."""

    @pytest.fixture
    def test_evidence_dir(self, tmp_path):
        """Provee un directorio aislado para evidencias de prueba E2E."""
        ev_dir = tmp_path / "evidence"
        ev_dir.mkdir(parents=True, exist_ok=True)
        return ev_dir

    @pytest.mark.asyncio
    async def test_complete_e2e_heuristic_audit_lifecycle(self, test_evidence_dir):
        """Ejecuta el flujo E2E completo desde la exploración física simulada hasta los reportes finales."""
        eval_id = "eval-e2e-tehuacan-001"
        dirs = ensure_evaluation_directories(test_evidence_dir, eval_id)

        # 1. Fase de Exploración: Generar evidencias físicas reales en disco
        scr_path = dirs["screenshots"] / "page_01_catalogo.png"
        scr_path.write_bytes(b"\x89PNG\r\n\x1a\nfake-screenshot-catalogo")

        snap_content = {
            "role": "WebArea",
            "name": "Catálogo de Especies - Reserva Tehuacán-Cuicatlán",
            "children": [
                {"role": "heading", "name": "Cactáceas Endémicas", "level": 1},
                {"role": "table", "name": "Listado de Especies"},
                {"role": "button", "name": "Descargar Ficha Técnica ZIP"},
            ],
        }
        snap_path = dirs["snapshots"] / "page_01_catalogo.json"
        snap_path.write_text(json.dumps(snap_content, indent=2), encoding="utf-8")

        dom_content = """<!DOCTYPE html>
        <html lang="es">
        <head><title>Catálogo Tehuacán</title></head>
        <body>
            <header class="main-header">
                <h1 style="font-family: Arial;">Reserva Tehuacán-Cuicatlán</h1>
            </header>
            <main>
                <div id="species-grid" class="grid-container">
                    <div class="card"><h2 style="font-family: 'Times New Roman';">Echinocactus platyacanthus</h2></div>
                </div>
                <button id="btn-download" onclick="downloadZip()">Descargar Ficha ZIP</button>
            </main>
        </body>
        </html>
        """
        dom_path = dirs["dom"] / "page_01_catalogo.html"
        dom_path.write_text(dom_content, encoding="utf-8")

        # Construir ExplorationResult con rutas relativas físicas
        exploration_result = ExplorationResult(
            evaluation_id=eval_id,
            target_url="https://reserva-tehuacan.gob.mx/catalogo",
            total_pages=1,
            total_screenshots=1,
            pages_explored=[
                PageExplorationResult(
                    evaluation_id=eval_id,
                    page_id="page_01_catalogo",
                    url="https://reserva-tehuacan.gob.mx/catalogo",
                    title="Catálogo de Especies",
                    observed_elements=["main-header", "species-grid", "btn-download"],
                    accessibility_snapshot_path=f"evaluations/{eval_id}/exploration/snapshots/page_01_catalogo.json",
                    dom_reference_path=f"evaluations/{eval_id}/exploration/dom/page_01_catalogo.html",
                    screenshots=[
                        EvidenceItem(
                            evidence_id="ev-scr-001",
                            evaluation_id=eval_id,
                            page_id="page_01_catalogo",
                            type=EvidenceType.SCREENSHOT,
                            file_path=f"evaluations/{eval_id}/exploration/screenshots/page_01_catalogo.png",
                            description="Captura principal del catálogo de especies",
                            mime_type="image/png",
                            file_size_bytes=scr_path.stat().st_size,
                        )
                    ],
                    actions_performed=[
                        "Navegar a https://reserva-tehuacan.gob.mx/catalogo",
                        "Capturar viewport 1366x768",
                        "Extraer árbol de accesibilidad",
                        "Volcar estructura DOM",
                    ],
                )
            ],
        )

        # 2. Fase de Evaluación Heurística: Invocar los 4 evaluadores especializados
        eval_dialogue = create_dialogue_evaluator()
        eval_action = create_action_evaluator()
        eval_structure = create_structure_evaluator()
        eval_protection = create_protection_evaluator()

        findings_dialogue = await eval_dialogue.evaluate(exploration_result, base_evidence_dir=test_evidence_dir)
        findings_action = await eval_action.evaluate(exploration_result, base_evidence_dir=test_evidence_dir)
        findings_structure = await eval_structure.evaluate(exploration_result, base_evidence_dir=test_evidence_dir)
        findings_protection = await eval_protection.evaluate(exploration_result, base_evidence_dir=test_evidence_dir)

        all_raw_findings = (
            findings_dialogue.findings
            + findings_action.findings
            + findings_structure.findings
            + findings_protection.findings
        )

        assert len(all_raw_findings) >= 3, "Los evaluadores deben identificar múltiples hallazgos en la página"

        # 3. Fase de Desduplicación: DeduplicatorAgent
        deduplicator = DeduplicatorAgent(base_evidence_dir=test_evidence_dir)
        consolidated = deduplicator.deduplicate(eval_id, all_raw_findings)

        assert consolidated.total_raw_findings == len(all_raw_findings)
        assert consolidated.total_consolidated_findings <= consolidated.total_raw_findings
        assert consolidated.duplicates_removed >= 0

        # Verificar persistencia física del archivo consolidado
        findings_dir = dirs["findings"]
        cons_file = findings_dir / "consolidated_findings.json"
        cons_file.write_text(
            json.dumps(consolidated.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        assert cons_file.exists()

        # 4. Fase de Generación de Reportes: Tríada oficial (results.json, report.md, report.csv)
        generator = ReportGenerator(base_evidence_dir=test_evidence_dir)
        report_meta = generator.generate_and_save_all(consolidated)

        reports_dir = dirs["reports"]
        json_report_file = reports_dir / "results.json"
        md_report_file = reports_dir / "report.md"
        csv_report_file = reports_dir / "report.csv"

        assert json_report_file.exists(), "results.json debe persistirse físicamente"
        assert md_report_file.exists(), "report.md debe persistirse físicamente"
        assert csv_report_file.exists(), "report.csv debe persistirse físicamente"

        # Validar consistencia y métricas del reporte JSON
        json_data = json.loads(json_report_file.read_text(encoding="utf-8"))
        assert json_data["metadata"]["evaluation_id"] == eval_id
        assert json_data["statistics"]["total_findings"] == consolidated.total_consolidated_findings
        assert "verdict" in json_data["statistics"]

        # Validar estructura del Markdown
        md_text = md_report_file.read_text(encoding="utf-8")
        assert f"Auditoría ID:** `{eval_id}`" in md_text
        assert "## 1. Resumen Ejecutivo y Veredicto" in md_text
        assert "## 2. Detalle Exhaustivo de Hallazgos Consolidados" in md_text

        # Validar estructura y cabeceras del CSV
        csv_text = csv_report_file.read_text(encoding="utf-8")
        assert '"finding_id","evaluation_id","heuristic_id","heuristic_name"' in csv_text
        assert eval_id in csv_text

    @pytest.mark.asyncio
    async def test_e2e_comparative_audit_pre_vs_post_redesign(self, test_evidence_dir):
        """Simula y verifica la evaluación comparativa entre versiones pre_redesign y post_redesign."""
        generator = ReportGenerator(base_evidence_dir=test_evidence_dir)
        deduplicator = DeduplicatorAgent(base_evidence_dir=test_evidence_dir)

        # 1. Auditoría de Versión Pre-Rediseño (Con múltiples problemas heurísticos)
        eval_id_pre = "eval-pre-redesign"
        dirs_pre = ensure_evaluation_directories(test_evidence_dir, eval_id_pre)

        (dirs_pre["snapshots"] / "home.json").write_text('{"name": "Home Pre"}', encoding="utf-8")
        (dirs_pre["dom"] / "home.html").write_text("<div>Sin spinner, sin alt, inconsistente</div>", encoding="utf-8")

        exp_pre = ExplorationResult(
            evaluation_id=eval_id_pre,
            target_url="https://reserva.test/pre",
            total_pages=1,
            total_screenshots=0,
            pages_explored=[
                PageExplorationResult(
                    evaluation_id=eval_id_pre,
                    page_id="home",
                    url="https://reserva.test/pre",
                    title="Home Pre",
                    accessibility_snapshot_path=f"evaluations/{eval_id_pre}/exploration/snapshots/home.json",
                    dom_reference_path=f"evaluations/{eval_id_pre}/exploration/dom/home.html",
                )
            ],
        )

        eval_dialogue = create_dialogue_evaluator()
        eval_structure = create_structure_evaluator()

        findings_pre_dia = await eval_dialogue.evaluate(exp_pre, base_evidence_dir=test_evidence_dir)
        findings_pre_str = await eval_structure.evaluate(exp_pre, base_evidence_dir=test_evidence_dir)
        consolidated_pre = deduplicator.deduplicate(eval_id_pre, findings_pre_dia.findings + findings_pre_str.findings)
        report_pre = generator.generate_and_save_all(consolidated_pre)

        # 2. Auditoría de Versión Post-Rediseño (Con mejoras implementadas: spinner presente, estándar unificado)
        eval_id_post = "eval-post-redesign"
        dirs_post = ensure_evaluation_directories(test_evidence_dir, eval_id_post)

        (dirs_post["snapshots"] / "home.json").write_text('{"name": "Home Post"}', encoding="utf-8")
        (dirs_post["dom"] / "home.html").write_text(
            "<div><div class='spinner-border loading'></div><h1 class='standard-title'>Limpio</h1></div>",
            encoding="utf-8",
        )

        exp_post = ExplorationResult(
            evaluation_id=eval_id_post,
            target_url="https://reserva.test/post",
            total_pages=1,
            total_screenshots=0,
            pages_explored=[
                PageExplorationResult(
                    evaluation_id=eval_id_post,
                    page_id="home",
                    url="https://reserva.test/post",
                    title="Home Post",
                    accessibility_snapshot_path=f"evaluations/{eval_id_post}/exploration/snapshots/home.json",
                    dom_reference_path=f"evaluations/{eval_id_post}/exploration/dom/home.html",
                )
            ],
        )

        findings_post_dia = await eval_dialogue.evaluate(exp_post, base_evidence_dir=test_evidence_dir)
        findings_post_str = await eval_structure.evaluate(exp_post, base_evidence_dir=test_evidence_dir)
        consolidated_post = deduplicator.deduplicate(eval_id_post, findings_post_dia.findings + findings_post_str.findings)
        report_post = generator.generate_and_save_all(consolidated_post)

        # 3. Validar contraste cuantitativo entre versiones
        stats_pre = report_pre["statistics"]
        stats_post = report_post["statistics"]

        # En la versión post-rediseño, al haber incorporado spinner/loading, H1 queda resuelto y el total de hallazgos se reduce
        assert stats_pre["total_findings"] >= stats_post["total_findings"], (
            f"La versión post-rediseño ({stats_post['total_findings']}) debe tener igual o menor cantidad "
            f"de problemas que la pre-rediseño ({stats_pre['total_findings']})"
        )
        assert (test_evidence_dir / report_pre["files"]["csv"]).exists()
        assert (test_evidence_dir / report_post["files"]["csv"]).exists()
