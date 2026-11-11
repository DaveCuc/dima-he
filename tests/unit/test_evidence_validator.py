"""Pruebas unitarias para el EvidenceValidatorAgent (patrón EscalationChecker) - Fase 5."""

import pytest
from pathlib import Path
from google.adk.agents.invocation_context import InvocationContext
from google.adk.sessions.session import Session
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from orchestrator.src.validators import EvidenceValidatorAgent
from shared.utils.file_paths import ensure_evaluation_directories


class TestEvidenceValidatorAgent:
    """Valida el comportamiento del EscalationChecker determinista."""

    @pytest.fixture
    def temp_evidence_dir(self, tmp_path):
        """Crea un directorio temporal para aislar pruebas de evidencias."""
        return tmp_path / "evidence"

    def _create_context(self, agent, session, invocation_id="inv1"):
        return InvocationContext(
            agent=agent,
            session=session,
            session_service=InMemorySessionService(),
            artifact_service=InMemoryArtifactService(),
            invocation_id=invocation_id,
        )

    @pytest.mark.asyncio
    async def test_escalation_when_all_evidences_exist_and_valid(self, temp_evidence_dir):
        """Verifica que el agente emita EventActions(escalate=True) cuando los 3 tipos de evidencia existen físicamente."""
        eval_id = "test-eval-escalate-ok"
        dirs = ensure_evaluation_directories(temp_evidence_dir, eval_id)

        # Crear archivos físicos no vacíos
        (dirs["screenshots"] / "capture.png").write_bytes(b"\x89PNG\r\n\x1a\nfake-screenshot")
        (dirs["snapshots"] / "a11y.json").write_text('{"root": {"role": "WebArea"}}', encoding="utf-8")
        (dirs["dom"] / "dom.html").write_text("<html><body><h1>Prueba</h1></body></html>", encoding="utf-8")

        agent = EvidenceValidatorAgent(
            name="test_validator",
            base_evidence_dir=temp_evidence_dir,
        )

        session = Session(id="s1", app_name="app", user_id="u1")
        session.state["evaluation_id"] = eval_id

        ctx = self._create_context(agent, session, "inv1")

        events = []
        async for event in agent.run_async(ctx):
            events.append(event)

        assert len(events) == 1
        ev = events[0]
        assert ev.author == "test_validator"
        assert ev.actions is not None
        assert ev.actions.escalate is True, "Debe escalar (romper el LoopAgent) cuando la evidencia es válida"

        assert session.state["evidence_validation"]["valid"] is True
        assert "exploration_feedback" not in session.state

    @pytest.mark.asyncio
    async def test_no_escalation_and_feedback_when_files_missing(self, temp_evidence_dir):
        """Verifica que no escale y registre feedback si faltan capturas o snapshots."""
        eval_id = "test-eval-missing"
        dirs = ensure_evaluation_directories(temp_evidence_dir, eval_id)

        # Solo crear el DOM, faltan screenshot y snapshot
        (dirs["dom"] / "dom.html").write_text("<html><body>Sin capturas</body></html>", encoding="utf-8")

        agent = EvidenceValidatorAgent(
            name="test_validator",
            base_evidence_dir=temp_evidence_dir,
        )

        session = Session(id="s2", app_name="app", user_id="u1")
        session.state["evaluation_id"] = eval_id

        ctx = self._create_context(agent, session, "inv2")

        events = []
        async for event in agent.run_async(ctx):
            events.append(event)

        assert len(events) == 1
        ev = events[0]
        assert ev.actions.escalate is False, "No debe escalar si faltan capturas"

        assert session.state["evidence_validation"]["valid"] is False
        assert "exploration_feedback" in session.state
        assert "captura" in session.state["exploration_feedback"].lower()

    @pytest.mark.asyncio
    async def test_no_escalation_when_files_are_empty(self, temp_evidence_dir):
        """Verifica que archivos de 0 bytes se consideren inválidos."""
        eval_id = "test-eval-empty-files"
        dirs = ensure_evaluation_directories(temp_evidence_dir, eval_id)

        # Archivo vacío (0 bytes)
        (dirs["screenshots"] / "empty.png").write_bytes(b"")
        (dirs["snapshots"] / "empty.json").write_text("", encoding="utf-8")
        (dirs["dom"] / "empty.html").write_text("", encoding="utf-8")

        agent = EvidenceValidatorAgent(
            name="test_validator",
            base_evidence_dir=temp_evidence_dir,
        )

        session = Session(id="s3", app_name="app", user_id="u1")
        session.state["evaluation_id"] = eval_id

        ctx = self._create_context(agent, session, "inv3")

        events = []
        async for event in agent.run_async(ctx):
            events.append(event)

        assert len(events) == 1
        assert events[0].actions.escalate is False
        assert session.state["evidence_validation"]["valid"] is False

    @pytest.mark.asyncio
    async def test_missing_evaluation_id_in_session(self, temp_evidence_dir):
        """Verifica que maneje apropiadamente la ausencia de evaluation_id."""
        agent = EvidenceValidatorAgent(base_evidence_dir=temp_evidence_dir)
        session = Session(id="s4", app_name="app", user_id="u1")
        ctx = self._create_context(agent, session, "inv4")

        events = []
        async for event in agent.run_async(ctx):
            events.append(event)

        assert len(events) == 1
        assert events[0].actions.escalate is False
        assert "evaluation_id" in session.state["exploration_feedback"]
