"""Pruebas unitarias para DeduplicatorAgent (Nodo 0)."""

import pytest
from pathlib import Path
from google.adk.agents.invocation_context import InvocationContext
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from orchestrator.src.deduplicator import DeduplicatorAgent
from shared.enums.agent_role import EvaluatorAgentId
from shared.enums.heuristics import HeuristicId
from shared.schemas.finding import ConsolidatedFindings, FindingLocation, UsabilityFinding


@pytest.fixture
def sample_findings():
    """Genera una lista de hallazgos brutos con duplicados intencionales."""
    f1 = UsabilityFinding(
        finding_id="find-dia-001",
        evaluation_id="eval-dedup-test",
        agent_id=EvaluatorAgentId.DIALOGUE,
        problem="Falta de indicador de carga visible",
        heuristic_id=HeuristicId.H1,
        heuristic_name="Visibilidad del estado del sistema",
        justification="No hay spinner o indicador mientras se cargan los contenidos dinámicos.",
        location=FindingLocation(page="home", element="MainContainer", selector="#main-content"),
        evidence_ids=["ev-scr-001"],
        severity=2,
        severity_justification="El usuario experimenta incertidumbre temporal.",
        improvement="Agregar un spinner de carga centrado.",
        confidence=0.85,
    )
    # f2 es un duplicado de f1 (mismo elemento, página y heurística), pero con mayor severidad y justificación más detallada
    f2 = UsabilityFinding(
        finding_id="find-act-002",
        evaluation_id="eval-dedup-test",
        agent_id=EvaluatorAgentId.ACTION,
        problem="Falta de indicador de carga visible durante la interacción",
        heuristic_id=HeuristicId.H1,
        heuristic_name="Visibilidad del estado del sistema",
        justification="No se proporciona retroalimentación inmediata tras activar el componente principal de búsqueda.",
        location=FindingLocation(page="home", element="MainContainer", selector="#main-content"),
        evidence_ids=["ev-scr-001", "ev-dom-002"],
        severity=3,
        severity_justification="El usuario cree que la interfaz se congeló y reintenta múltiples veces.",
        improvement="Implementar skeleton loader y barra de progreso.",
        confidence=0.95,
    )
    # f3 es un hallazgo único independiente
    f3 = UsabilityFinding(
        finding_id="find-str-003",
        evaluation_id="eval-dedup-test",
        agent_id=EvaluatorAgentId.STRUCTURE,
        problem="Inconsistencia tipográfica en encabezados",
        heuristic_id=HeuristicId.H4,
        heuristic_name="Consistencia y estándares",
        justification="Los títulos h2 utilizan fuentes y tamaños no estandarizados respecto a la guía de estilo.",
        location=FindingLocation(page="catalog", element="CardHeader", selector=".card-title"),
        evidence_ids=["ev-scr-003"],
        severity=1,
        severity_justification="Problema meramente cosmético.",
        improvement="Unificar estilos con clases CSS utilitarias globales.",
        confidence=0.90,
    )
    return [f1, f2, f3]


class TestDeduplicatorAgent:
    """Valida la lógica determinista de desduplicación y consolidación de hallazgos."""

    def test_deduplicate_groups_identical_problems_and_takes_max_severity(self, sample_findings):
        deduplicator = DeduplicatorAgent()
        consolidated = deduplicator.deduplicate("eval-dedup-test", sample_findings)

        assert isinstance(consolidated, ConsolidatedFindings)
        assert consolidated.total_raw_findings == 3
        assert consolidated.total_consolidated_findings == 2, "Debe consolidar los 2 duplicados en 1 hallazgo único"
        assert consolidated.duplicates_removed == 1

        # Encontrar el hallazgo fusionado correspondiente a H1
        h1_finding = next(f for f in consolidated.findings if f.heuristic_id == HeuristicId.H1)
        assert h1_finding.severity == 3, "Debe preservar la máxima severidad entre los duplicados (3)"
        assert len(h1_finding.source_agents) == 2, "Debe preservar los dos agentes de origen"
        assert EvaluatorAgentId.DIALOGUE in h1_finding.source_agents
        assert EvaluatorAgentId.ACTION in h1_finding.source_agents
        assert "find-dia-001" in h1_finding.original_finding_ids
        assert "find-act-002" in h1_finding.original_finding_ids
        assert set(h1_finding.evidence_ids) == {"ev-scr-001", "ev-dom-002"}
        assert h1_finding.confidence == 0.90, "Promedio de 0.85 y 0.95 debe ser 0.90"

    def test_deduplicate_empty_findings(self):
        deduplicator = DeduplicatorAgent()
        consolidated = deduplicator.deduplicate("eval-empty", [])
        assert consolidated.total_raw_findings == 0
        assert consolidated.total_consolidated_findings == 0
        assert consolidated.duplicates_removed == 0
        assert len(consolidated.findings) == 0

    @pytest.mark.asyncio
    async def test_deduplicator_agent_adk_invocation_and_persistence(self, tmp_path, sample_findings):
        temp_evidence = tmp_path / "evidence"
        deduplicator = DeduplicatorAgent(base_evidence_dir=temp_evidence)

        session_service = InMemorySessionService()
        session = await session_service.create_session(
            app_name="orchestrator",
            user_id="dima_user",
            state={
                "evaluation_id": "eval-adk-dedup",
                "findings_dialogue": [sample_findings[0].model_dump(mode="json")],
                "findings_action": [sample_findings[1].model_dump(mode="json")],
                "findings_structure": [sample_findings[2].model_dump(mode="json")],
                "findings_protection": [],
            },
        )

        ctx = InvocationContext(
            agent=deduplicator,
            session=session,
            session_service=session_service,
            artifact_service=InMemoryArtifactService(),
            invocation_id="inv1",
        )

        events = []
        async for event in deduplicator._run_async_impl(ctx):
            events.append(event)

        assert len(events) == 1
        ev = events[0]
        assert ev.actions is not None
        assert "consolidated_findings" in ev.actions.state_delta
        assert ev.actions.state_delta["total_consolidated_findings"] == 2
        assert ev.actions.state_delta["duplicates_removed"] == 1

        # Verificar persistencia física en disco
        persisted_file = temp_evidence / "evaluations" / "eval-adk-dedup" / "findings" / "consolidated_findings.json"
        assert persisted_file.exists(), f"El archivo consolidado debe existir en {persisted_file}"
        assert "Falta de indicador de carga visible" in persisted_file.read_text(encoding="utf-8")
