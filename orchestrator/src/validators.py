"""Agente validador determinista de evidencias para el Orquestador (Nodo 0).

Implementa el patrón EscalationChecker de Google ADK mediante BaseAgent (Python puro).
Verifica físicamente en disco la integridad y existencia de capturas, snapshots
y volcados DOM antes de permitir la transición a los nodos evaluadores.
"""

import logging
from pathlib import Path
from typing import AsyncGenerator, Optional, Union

from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types as genai_types

from shared.utils.file_paths import get_exploration_dir

logger = logging.getLogger(__name__)


class EvidenceValidatorAgent(BaseAgent):
    """Agente determinista que inspecciona físicamente el volumen de evidencias.

    Si las evidencias físicas existen y son válidas, emite EventActions(escalate=True)
    para romper el LoopAgent de exploración y avanzar a la fase de evaluación.
    Si fallan, escribe retroalimentación en ctx.session.state["exploration_feedback"]
    y permite que el bucle reintente hasta max_iterations.
    """

    base_evidence_dir: str = "evidence"

    def __init__(
        self,
        name: str = "evidence_validator_agent",
        base_evidence_dir: Union[str, Path] = "evidence",
        **kwargs,
    ):
        super().__init__(
            name=name,
            description="Valida físicamente la presencia e integridad de capturas, snapshots y DOM en disco.",
            **kwargs,
        )
        self.base_evidence_dir = str(base_evidence_dir)

    def validate_physical_evidence(self, evaluation_id: str) -> tuple[bool, str]:
        """Comprueba físicamente la presencia de capturas, snapshots y DOM no vacíos."""
        exploration_path = get_exploration_dir(self.base_evidence_dir, evaluation_id)
        if not exploration_path.exists():
            return False, f"El directorio de exploración no existe: {exploration_path}"

        screenshots_dir = exploration_path / "screenshots"
        snapshots_dir = exploration_path / "snapshots"
        dom_dir = exploration_path / "dom"

        # 1. Validar capturas de pantalla
        screenshots = list(screenshots_dir.glob("*.png")) if screenshots_dir.exists() else []
        valid_screenshots = [s for s in screenshots if s.stat().st_size > 0]
        if not valid_screenshots:
            return False, "No se encontraron archivos de captura (.png) no vacíos en disco."

        # 2. Validar snapshots de accesibilidad
        snapshots = list(snapshots_dir.glob("*.json")) if snapshots_dir.exists() else []
        valid_snapshots = [s for s in snapshots if s.stat().st_size > 0]
        if not valid_snapshots:
            return False, "No se encontraron snapshots de accesibilidad (.json) no vacíos en disco."

        # 3. Validar volcados del DOM
        dom_dumps = list(dom_dir.glob("*.html")) if dom_dir.exists() else []
        valid_dom = [d for d in dom_dumps if d.stat().st_size > 0]
        if not valid_dom:
            return False, "No se encontraron volcados de DOM (.html) no vacíos en disco."

        details = (
            f"Evidencias físicas verificadas: {len(valid_screenshots)} capturas, "
            f"{len(valid_snapshots)} snapshots, {len(valid_dom)} volcados DOM."
        )
        return True, details

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """Ejecuta la validación determinista e interactúa con el bucle mediante EventActions."""
        # Extraer evaluation_id desde el estado de la sesión o el payload
        state = ctx.session.state if ctx.session else {}
        eval_id = state.get("evaluation_id")
        if not eval_id and "evaluation_request" in state:
            req_data = state["evaluation_request"]
            if isinstance(req_data, dict):
                eval_id = req_data.get("evaluation_id")
            elif hasattr(req_data, "evaluation_id"):
                eval_id = req_data.evaluation_id

        if not eval_id:
            logger.warning("EvidenceValidatorAgent: No se encontró 'evaluation_id' en la sesión.")
            state["exploration_feedback"] = "No se proporcionó evaluation_id para verificar evidencias."
            yield Event(
                author=self.name,
                content=genai_types.Content(
                    parts=[genai_types.Part.from_text(text="Falta evaluation_id en la sesión.")]
                ),
                actions=EventActions(escalate=False),
            )
            return

        is_valid, message = self.validate_physical_evidence(eval_id)

        if is_valid:
            logger.info(f"EvidenceValidatorAgent: Validación exitosa para [{eval_id}]. Escalando bucle.")
            state["evidence_validation"] = {"valid": True, "details": message}
            state.pop("exploration_feedback", None)

            yield Event(
                author=self.name,
                content=genai_types.Content(
                    parts=[genai_types.Part.from_text(text=f"Validación física exitosa: {message}")]
                ),
                actions=EventActions(
                    escalate=True,
                    state_delta={
                        "evidence_validation": {"valid": True, "details": message},
                        "exploration_feedback": None,
                    },
                ),
            )
        else:
            logger.warning(f"EvidenceValidatorAgent: Validación fallida para [{eval_id}]: {message}")
            state["evidence_validation"] = {"valid": False, "reason": message}
            state["exploration_feedback"] = f"Reintentar exploración. Motivo: {message}"

            yield Event(
                author=self.name,
                content=genai_types.Content(
                    parts=[genai_types.Part.from_text(text=f"Validación física incompleta: {message}")]
                ),
                actions=EventActions(
                    escalate=False,
                    state_delta={
                        "evidence_validation": {"valid": False, "reason": message},
                        "exploration_feedback": f"Reintentar exploración. Motivo: {message}",
                    },
                ),
            )
