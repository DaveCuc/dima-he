"""Pruebas unitarias para los 4 Evaluadores Heurísticos (Fase 6)."""

import pytest
from pathlib import Path
from evaluators.dialogue.src.agent import create_dialogue_evaluator
from evaluators.action.src.agent import create_action_evaluator
from evaluators.structure.src.agent import create_structure_evaluator
from evaluators.protection.src.agent import create_protection_evaluator
from shared.enums.agent_role import EvaluatorAgentId
from shared.enums.evidence_type import EvidenceType
from shared.schemas.evidence import EvidenceItem
from shared.schemas.exploration import ExplorationResult, PageExplorationResult
from shared.schemas.finding import EvaluatorFindingList
from shared.utils.file_paths import ensure_evaluation_directories


class TestHeuristicEvaluatorsUnit:
    """Valida la configuración, carga multimodal e inferencia de los Nodos 2 al 5."""

    @pytest.fixture
    def mock_exploration_data(self, tmp_path):
        """Crea evidencias físicas reales para probar la carga multimodal."""
        eval_id = "eval-test-evaluators"
        dirs = ensure_evaluation_directories(tmp_path, eval_id)

        # Crear archivos físicos de prueba
        scr_path = dirs["screenshots"] / "page_01_home.png"
        scr_path.write_bytes(b"\x89PNG\r\n\x1a\nfake-image-bytes-for-test")

        snap_path = dirs["snapshots"] / "page_01_home.json"
        snap_path.write_text('{"role": "WebArea", "name": "Reserva Tehuacán"}', encoding="utf-8")

        dom_path = dirs["dom"] / "page_01_home.html"
        dom_path.write_text("<html><body><h1>Reserva Biosfera</h1><main><button>Aceptar</button></main></body></html>", encoding="utf-8")

        screenshot_item = EvidenceItem(
            evidence_id="ev-scr-001",
            type=EvidenceType.SCREENSHOT,
            evaluation_id=eval_id,
            page_id="page_01_home",
            file_path=f"evaluations/{eval_id}/exploration/screenshots/page_01_home.png",
            mime_type="image/png",
            sha256="abc123hash",
            description="Captura de página de inicio",
        )

        page_result = PageExplorationResult(
            evaluation_id=eval_id,
            page_id="page_01_home",
            url="http://host.docker.internal:8000/",
            title="Reserva Tehuacán",
            accessibility_snapshot_path=f"evaluations/{eval_id}/exploration/snapshots/page_01_home.json",
            dom_reference_path=f"evaluations/{eval_id}/exploration/dom/page_01_home.html",
            screenshots=[screenshot_item],
            actions_performed=["Navegar a http://host.docker.internal:8000/"],
        )

        exploration_result = ExplorationResult(
            evaluation_id=eval_id,
            target_url="http://host.docker.internal:8000/",
            pages_explored=[page_result],
            total_pages=1,
            total_screenshots=1,
        )
        return exploration_result, tmp_path

    def test_evaluator_heuristics_distribution(self):
        """Verifica que cada evaluador tenga asignadas las heurísticas especificadas en Blueprint v2.0."""
        dialogue = create_dialogue_evaluator()
        action = create_action_evaluator()
        structure = create_structure_evaluator()
        protection = create_protection_evaluator()

        # Nodo 2: Diálogo
        assert dialogue.node_id == EvaluatorAgentId.DIALOGUE
        assert set(dialogue.heuristics) == {"H1", "H2", "H10"}
        assert dialogue.port == 8002

        # Nodo 3: Acción
        assert action.node_id == EvaluatorAgentId.ACTION
        assert set(action.heuristics) == {"H3", "H7"}
        assert action.port == 8003

        # Nodo 4: Estructura
        assert structure.node_id == EvaluatorAgentId.STRUCTURE
        assert set(structure.heuristics) == {"H4", "H6", "H8"}
        assert structure.port == 8004

        # Nodo 5: Protección
        assert protection.node_id == EvaluatorAgentId.PROTECTION
        assert set(protection.heuristics) == {"H5", "H9"}
        assert protection.port == 8005

    def test_multimodal_evidence_loading_from_disk(self, mock_exploration_data):
        """Verifica que load_multimodal_evidence lea las capturas como bytes y arme partes válidas."""
        exploration_result, temp_dir = mock_exploration_data
        dialogue = create_dialogue_evaluator()

        parts = dialogue.load_multimodal_evidence(exploration_result, base_evidence_dir=temp_dir)
        assert len(parts) >= 2, "Debe cargar al menos texto de contexto y la captura binaria"

        # Verificar que una de las partes sea de tipo bytes/imagen
        has_image_part = any(getattr(p, "inline_data", None) is not None for p in parts)
        assert has_image_part is True, "Debe incluir al menos una parte inline_data con la captura"

    @pytest.mark.asyncio
    async def test_dialogue_evaluation_generates_valid_findings(self, mock_exploration_data):
        """Verifica que el evaluador de diálogo retorne EvaluatorFindingList válido."""
        exploration_result, temp_dir = mock_exploration_data
        dialogue = create_dialogue_evaluator()

        findings = await dialogue.evaluate(exploration_result, base_evidence_dir=temp_dir)
        assert isinstance(findings, EvaluatorFindingList)
        assert len(findings.findings) > 0

        for f in findings.findings:
            assert f.agent_id == EvaluatorAgentId.DIALOGUE
            assert f.heuristic_id.value in ["H1", "H2", "H10"]
            assert 0 <= f.severity <= 4
            assert len(f.problem) > 0
            assert len(f.improvement) > 0

    @pytest.mark.asyncio
    async def test_action_evaluation_generates_valid_findings(self, mock_exploration_data):
        """Verifica que el evaluador de acción retorne hallazgos de H3 o H7."""
        exploration_result, temp_dir = mock_exploration_data
        action = create_action_evaluator()

        findings = await action.evaluate(exploration_result, base_evidence_dir=temp_dir)
        assert isinstance(findings, EvaluatorFindingList)
        assert len(findings.findings) > 0

        for f in findings.findings:
            assert f.agent_id == EvaluatorAgentId.ACTION
            assert f.heuristic_id.value in ["H3", "H7"]
            assert 0 <= f.severity <= 4

    @pytest.mark.asyncio
    async def test_structure_evaluation_generates_valid_findings(self, mock_exploration_data):
        """Verifica que el evaluador de estructura retorne hallazgos de H4, H6 u H8."""
        exploration_result, temp_dir = mock_exploration_data
        structure = create_structure_evaluator()

        findings = await structure.evaluate(exploration_result, base_evidence_dir=temp_dir)
        assert isinstance(findings, EvaluatorFindingList)
        assert len(findings.findings) > 0

        for f in findings.findings:
            assert f.agent_id == EvaluatorAgentId.STRUCTURE
            assert f.heuristic_id.value in ["H4", "H6", "H8"]
            assert 0 <= f.severity <= 4

    @pytest.mark.asyncio
    async def test_protection_evaluation_generates_valid_findings(self, mock_exploration_data):
        """Verifica que el evaluador de protección retorne hallazgos de H5 o H9."""
        exploration_result, temp_dir = mock_exploration_data
        protection = create_protection_evaluator()

        findings = await protection.evaluate(exploration_result, base_evidence_dir=temp_dir)
        assert isinstance(findings, EvaluatorFindingList)
        assert len(findings.findings) > 0

        for f in findings.findings:
            assert f.agent_id == EvaluatorAgentId.PROTECTION
            assert f.heuristic_id.value in ["H5", "H9"]
            assert 0 <= f.severity <= 4

    def test_adk_agent_configuration_strictness(self):
        """Verifica que cada agente ADK tenga las restricciones requeridas."""
        evaluators = [
            create_dialogue_evaluator(),
            create_action_evaluator(),
            create_structure_evaluator(),
            create_protection_evaluator(),
        ]
        for ev in evaluators:
            agent = ev.create_adk_agent()
            assert agent.disallow_transfer_to_parent is True
            assert agent.disallow_transfer_to_peers is True
            assert agent.output_schema == EvaluatorFindingList
