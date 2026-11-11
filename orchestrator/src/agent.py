"""Definición del flujo de orquestación en Google ADK para el Nodo 0 (Orchestrator).

Implementa el ciclo determinista de extracción de evidencias (exploration_loop)
mediante LoopAgent con max_iterations=3, coordinando al RemoteWebExplorerAgent y al
EvidenceValidatorAgent (patrón EscalationChecker).
"""

import logging
import os
from typing import Any, Dict, Optional, Union
from pathlib import Path

from google.adk.agents.loop_agent import LoopAgent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.auth.credential_service.in_memory_credential_service import InMemoryCredentialService
from google.genai import types as genai_types

from shared.schemas.evaluation import EvaluationRequest
from shared.schemas.exploration import ExplorationResult
from orchestrator.src.remote_nodes import RemoteWebExplorerAgent, DEFAULT_WEB_EXPLORER_URL
from orchestrator.src.validators import EvidenceValidatorAgent

logger = logging.getLogger(__name__)

DEFAULT_EVIDENCE_DIR = os.getenv(
    "EVIDENCE_DIR",
    "/app/evidence" if os.path.exists("/app/evidence") else "evidence"
)


def create_exploration_loop(
    web_explorer_url: str = DEFAULT_WEB_EXPLORER_URL,
    base_evidence_dir: Union[str, Path] = DEFAULT_EVIDENCE_DIR,
    max_iterations: int = 3,
) -> LoopAgent:
    """Crea el LoopAgent determinista de exploración y validación física de evidencias."""
    remote_explorer = RemoteWebExplorerAgent(
        name="remote_web_explorer",
        endpoint_url=web_explorer_url,
    )
    evidence_validator = EvidenceValidatorAgent(
        name="evidence_validator_agent",
        base_evidence_dir=base_evidence_dir,
    )

    exploration_loop = LoopAgent(
        name="exploration_loop",
        description="Ciclo iterativo de navegación web y validación física de evidencias con EscalationChecker.",
        sub_agents=[remote_explorer, evidence_validator],
        max_iterations=max_iterations,
    )
    return exploration_loop


async def execute_orchestrated_exploration(
    request: EvaluationRequest,
    web_explorer_url: str = DEFAULT_WEB_EXPLORER_URL,
    base_evidence_dir: Union[str, Path] = DEFAULT_EVIDENCE_DIR,
    max_iterations: int = 3,
) -> Dict[str, Any]:
    """Ejecuta el ciclo de exploración orquestado mediante Google ADK Runner y servicios en memoria."""
    loop_agent = create_exploration_loop(
        web_explorer_url=web_explorer_url,
        base_evidence_dir=base_evidence_dir,
        max_iterations=max_iterations,
    )

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="orchestrator",
        user_id="dima_user",
        state={
            "evaluation_id": request.evaluation_id,
            "evaluation_request": request.model_dump(mode="json"),
            "target_url": request.target_url,
        },
    )

    runner = Runner(
        app_name="orchestrator",
        agent=loop_agent,
        session_service=session_service,
        memory_service=InMemoryMemoryService(),
        artifact_service=InMemoryArtifactService(),
        credential_service=InMemoryCredentialService(),
    )

    logger.info(f"Iniciando ciclo de orquestación para {request.target_url} (Eval ID: {request.evaluation_id})")

    # Disparar la ejecución del bucle
    user_content = genai_types.Content(
        parts=[genai_types.Part.from_text(text=f"Iniciar evaluación heurística para {request.target_url}")]
    )

    async for event in runner.run_async(
        session_id=session.id,
        user_id="dima_user",
        new_message=user_content,
    ):
        logger.debug(f"Evento emitido por [{event.author}]: actions.escalate={event.actions.escalate if event.actions else False}")

    final_session = await session_service.get_session(
        app_name="orchestrator",
        user_id="dima_user",
        session_id=session.id,
    )
    final_state = final_session.state if final_session else {}

    validation = final_state.get("evidence_validation", {})
    exploration = final_state.get("exploration_result")

    return {
        "evaluation_id": request.evaluation_id,
        "is_valid": validation.get("valid", False),
        "validation_details": validation.get("details") or validation.get("reason"),
        "exploration_result": exploration,
        "session_state": final_state,
    }
