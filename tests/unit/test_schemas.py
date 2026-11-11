"""Pruebas unitarias para contratos Pydantic v2 en shared/schemas/."""

import pytest
from pydantic import ValidationError
from shared.enums.agent_role import EvaluatorAgentId, EvaluationVersion
from shared.enums.evidence_type import EvidenceType
from shared.enums.heuristics import HeuristicId
from shared.schemas.evaluation import (
    EvaluationRequest,
    EvaluationScope,
    ViewportConfig,
    AuthCredentials,
)
from shared.schemas.evidence import EvidenceItem
from shared.schemas.exploration import PageExplorationResult, ExplorationResult
from shared.schemas.finding import (
    FindingLocation,
    UsabilityFinding,
    EvaluatorFindingList,
    ConsolidatedFinding,
    ConsolidatedFindings,
)


class TestEvaluationSchemas:
    """Pruebas de contratos para EvaluationRequest y ViewportConfig."""

    def test_valid_evaluation_request(self):
        req = EvaluationRequest(
            evaluation_id="eval-001",
            target_url="http://host.docker.internal:8000",
            version=EvaluationVersion.PRE_REDESIGN,
            scope=EvaluationScope(
                pages=["/catalogo", "/tours"],
                max_depth=1,
            ),
        )
        assert req.evaluation_id == "eval-001"
        assert req.target_url == "http://host.docker.internal:8000"
        assert req.version == EvaluationVersion.PRE_REDESIGN
        assert req.viewport.width == 1366
        assert req.viewport.height == 768

    def test_invalid_target_url_scheme(self):
        with pytest.raises(ValidationError) as exc:
            EvaluationRequest(
                evaluation_id="eval-001",
                target_url="ftp://invalid-url.com",
            )
        assert "target_url" in str(exc.value)

    def test_invalid_evaluation_id_characters(self):
        with pytest.raises(ValidationError) as exc:
            EvaluationRequest(
                evaluation_id="eval/001 with spaces",
                target_url="http://localhost:8000",
            )
        assert "evaluation_id" in str(exc.value)

    def test_viewport_boundaries(self):
        with pytest.raises(ValidationError):
            ViewportConfig(width=100)  # ge=320

        with pytest.raises(ValidationError):
            ViewportConfig(height=5000)  # le=2160


class TestEvidenceSchemas:
    """Pruebas de contratos de evidencias y guardrail anti-Base64."""

    def test_valid_evidence_item(self):
        item = EvidenceItem(
            evidence_id="ev-001",
            type=EvidenceType.SCREENSHOT,
            file_path="evaluations/eval-001/exploration/screenshots/shot_01.png",
            page_id="page-home",
            description="Captura de vista principal",
        )
        assert item.evidence_id == "ev-001"
        assert item.type == EvidenceType.SCREENSHOT
        assert item.file_path == "evaluations/eval-001/exploration/screenshots/shot_01.png"

    def test_path_normalization_to_posix(self):
        # Rutas generadas con backslash en Windows deben normalizarse a POSIX
        item = EvidenceItem(
            evidence_id="ev-002",
            type=EvidenceType.DOM,
            file_path="evaluations\\eval-001\\exploration\\dom\\home.html",
            page_id="page-home",
            description="Volcado DOM",
        )
        assert "\\" not in item.file_path
        assert item.file_path == "evaluations/eval-001/exploration/dom/home.html"

    def test_prohibition_of_base64_payload(self):
        """Verifica el guardrail duro: Prohibido Base64 en A2A."""
        with pytest.raises(ValidationError) as exc:
            EvidenceItem(
                evidence_id="ev-invalid",
                type=EvidenceType.SCREENSHOT,
                file_path="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
                page_id="page-home",
                description="Intento inválido con Base64",
            )
        assert "Guardrail A2A violado" in str(exc.value)


class TestExplorationSchemas:
    """Pruebas de contratos de resultados de exploración."""

    def test_page_exploration_result_defaults(self):
        page_res = PageExplorationResult(
            evaluation_id="eval-001",
            page_id="page-home",
            url="http://host.docker.internal:8000/",
            title="Reserva Tehuacán-Cuicatlán",
        )
        assert page_res.observed_elements == []
        assert page_res.screenshots == []
        assert page_res.errors == []

    def test_exploration_result_aggregation(self):
        page_res = PageExplorationResult(
            evaluation_id="eval-001",
            page_id="page-home",
            url="http://host.docker.internal:8000/",
        )
        exp = ExplorationResult(
            evaluation_id="eval-001",
            target_url="http://host.docker.internal:8000",
            pages_explored=[page_res],
            total_pages=1,
            total_screenshots=0,
            total_errors=0,
        )
        assert exp.total_pages == 1
        assert len(exp.pages_explored) == 1


class TestFindingSchemas:
    """Pruebas de contratos de hallazgos, severidad y salida de evaluadores."""

    def test_valid_usability_finding(self):
        finding = UsabilityFinding(
            finding_id="find-001",
            evaluation_id="eval-001",
            agent_id=EvaluatorAgentId.DIALOGUE,
            problem="Falta de indicador visual de carga al filtrar resultados",
            heuristic_id=HeuristicId.H1,
            justification="Al pulsar el botón 'Filtrar', la interfaz no proporciona retroalimentación.",
            location=FindingLocation(
                page="page-catalog",
                element="Botón Filtrar",
                selector="button#btn-filter",
            ),
            severity=2,
            severity_justification="Genera incertidumbre leve pero la búsqueda finalmente carga.",
            improvement="Añadir un spinner o estado disabled en el botón durante la petición.",
            evidence_ids=["ev-001"],
        )
        assert finding.finding_id == "find-001"
        assert finding.heuristic_name == "Visibilidad del estado del sistema"
        assert finding.severity == 2

    def test_severity_boundary_validation(self):
        """Verifica que la severidad de Nielsen solo acepte valores entre 0 y 4."""
        with pytest.raises(ValidationError):
            UsabilityFinding(
                finding_id="find-invalid",
                evaluation_id="eval-001",
                agent_id=EvaluatorAgentId.ACTION,
                problem="Problema X",
                heuristic_id=HeuristicId.H3,
                justification="Justificación X",
                location=FindingLocation(page="p1", element="e1"),
                severity=5,  # Fuera de rango (máximo 4)
                severity_justification="J5",
                improvement="I5",
            )

        with pytest.raises(ValidationError):
            UsabilityFinding(
                finding_id="find-invalid-negative",
                evaluation_id="eval-001",
                agent_id=EvaluatorAgentId.ACTION,
                problem="Problema X",
                heuristic_id=HeuristicId.H3,
                justification="Justificación X",
                location=FindingLocation(page="p1", element="e1"),
                severity=-1,  # Fuera de rango (mínimo 0)
                severity_justification="J_neg",
                improvement="I_neg",
            )

    def test_evaluator_finding_list_serialization(self):
        finding = UsabilityFinding(
            finding_id="find-001",
            evaluation_id="eval-001",
            agent_id=EvaluatorAgentId.PROTECTION,
            problem="El formulario no advierte antes de borrar un registro",
            heuristic_id=HeuristicId.H5,
            justification="Falta confirmación en acción irreversible.",
            location=FindingLocation(page="page-admin", element="Botón Eliminar"),
            severity=3,
            severity_justification="Pérdida potencial de datos.",
            improvement="Agregar modal de confirmación antes de enviar DELETE.",
        )
        finding_list = EvaluatorFindingList(findings=[finding])
        json_data = finding_list.model_dump_json()
        assert "find-001" in json_data
        assert "evaluator_protection" in json_data

        # Deserialización simétrica
        restored = EvaluatorFindingList.model_validate_json(json_data)
        assert len(restored.findings) == 1
        assert restored.findings[0].heuristic_id == HeuristicId.H5

    def test_consolidated_findings_traceability(self):
        cons_finding = ConsolidatedFinding(
            finding_id="find-cons-001",
            evaluation_id="eval-001",
            agent_id=EvaluatorAgentId.STRUCTURE,
            problem="Menú con iconos sin texto ni tooltips",
            heuristic_id=HeuristicId.H6,
            justification="Obliga a recordar la función de iconos ambiguos.",
            location=FindingLocation(page="page-nav", element="Barra lateral"),
            severity=2,
            severity_justification="Molestia menor.",
            improvement="Agregar etiquetas visibles o tooltip accesible.",
            source_agents=[EvaluatorAgentId.STRUCTURE, EvaluatorAgentId.DIALOGUE],
            original_finding_ids=["find-str-001", "find-dia-004"],
        )
        report_data = ConsolidatedFindings(
            evaluation_id="eval-001",
            findings=[cons_finding],
            total_raw_findings=2,
            total_consolidated_findings=1,
            duplicates_removed=1,
        )
        assert len(report_data.findings[0].source_agents) == 2
        assert len(report_data.findings[0].original_finding_ids) == 2
        assert report_data.duplicates_removed == 1
