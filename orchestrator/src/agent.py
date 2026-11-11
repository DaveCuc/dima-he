"""Definición del flujo de orquestación en Google ADK para el Nodo 0 (Orchestrator).

Implementa:
1. El ciclo determinista de extracción de evidencias (exploration_loop) mediante
   LoopAgent con max_iterations=3 y EvidenceValidatorAgent (patrón EscalationChecker).
2. La ejecución concurrente de los 4 evaluadores heurísticos mediante ParallelAgent.
3. El pipeline secuencial raíz (root_agent) mediante SequentialAgent.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from google.adk.agents.loop_agent import LoopAgent
from google.adk.agents.parallel_agent import ParallelAgent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.auth.credential_service.in_memory_credential_service import InMemoryCredentialService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types as genai_types

from orchestrator.src.remote_nodes import (
    DEFAULT_EVALUATOR_URLS,
    DEFAULT_WEB_EXPLORER_URL,
    RemoteEvaluatorAgent,
    RemoteWebExplorerAgent,
)
from orchestrator.src.validators import EvidenceValidatorAgent
from shared.schemas.evaluation import EvaluationRequest
from shared.schemas.exploration import ExplorationResult

logger = logging.getLogger(__name__)

DEFAULT_EVIDENCE_DIR = os.getenv(
    "EVIDENCE_DIR",
    "/app/evidence" if os.path.exists("/app/evidence") else "evidence",
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


def create_parallel_evaluators(
    evaluator_urls: Optional[Dict[str, str]] = None,
) -> ParallelAgent:
    """Crea el ParallelAgent que dispara concurrentemente las llamadas A2A hacia los 4 evaluadores."""
    urls = evaluator_urls or DEFAULT_EVALUATOR_URLS

    eval_dialogue = RemoteEvaluatorAgent(
        name="remote_dialogue",
        dimension="dialogue",
        endpoint_url=urls.get("dialogue", DEFAULT_EVALUATOR_URLS["dialogue"]),
    )
    eval_action = RemoteEvaluatorAgent(
        name="remote_action",
        dimension="action",
        endpoint_url=urls.get("action", DEFAULT_EVALUATOR_URLS["action"]),
    )
    eval_structure = RemoteEvaluatorAgent(
        name="remote_structure",
        dimension="structure",
        endpoint_url=urls.get("structure", DEFAULT_EVALUATOR_URLS["structure"]),
    )
    eval_protection = RemoteEvaluatorAgent(
        name="remote_protection",
        dimension="protection",
        endpoint_url=urls.get("protection", DEFAULT_EVALUATOR_URLS["protection"]),
    )

    parallel_agent = ParallelAgent(
        name="parallel_evaluators",
        description="Ejecuta en paralelo las evaluaciones heurísticas de Diálogo, Acción, Estructura y Protección.",
        sub_agents=[eval_dialogue, eval_action, eval_structure, eval_protection],
    )
    return parallel_agent


def create_orchestrator_pipeline(
    web_explorer_url: str = DEFAULT_WEB_EXPLORER_URL,
    evaluator_urls: Optional[Dict[str, str]] = None,
    base_evidence_dir: Union[str, Path] = DEFAULT_EVIDENCE_DIR,
    max_iterations: int = 3,
) -> SequentialAgent:
    """Construye la columna vertebral SequentialAgent: [exploration_loop, parallel_evaluators]."""
    exploration_loop = create_exploration_loop(
        web_explorer_url=web_explorer_url,
        base_evidence_dir=base_evidence_dir,
        max_iterations=max_iterations,
    )
    parallel_evaluators = create_parallel_evaluators(evaluator_urls=evaluator_urls)

    root_agent = SequentialAgent(
        name="orchestrator_pipeline",
        description="Pipeline maestro de evaluación heurística distribuida.",
        sub_agents=[exploration_loop, parallel_evaluators],
    )
    return root_agent


async def execute_orchestrated_exploration(
    request: EvaluationRequest,
    web_explorer_url: str = DEFAULT_WEB_EXPLORER_URL,
    base_evidence_dir: Union[str, Path] = DEFAULT_EVIDENCE_DIR,
    max_iterations: int = 3,
) -> Dict[str, Any]:
    """Ejecuta únicamente el ciclo de exploración orquestado (usado en Fase 5)."""
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

    logger.info(f"Iniciando ciclo de exploración para {request.target_url} (Eval ID: {request.evaluation_id})")

    user_content = genai_types.Content(
        parts=[genai_types.Part.from_text(text=f"Iniciar exploración para {request.target_url}")]
    )

    async for event in runner.run_async(
        session_id=session.id,
        user_id="dima_user",
        new_message=user_content,
    ):
        pass

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


async def execute_orchestrated_evaluation(
    request: EvaluationRequest,
    web_explorer_url: str = DEFAULT_WEB_EXPLORER_URL,
    evaluator_urls: Optional[Dict[str, str]] = None,
    base_evidence_dir: Union[str, Path] = DEFAULT_EVIDENCE_DIR,
    max_iterations: int = 3,
) -> Dict[str, Any]:
    """Ejecuta el pipeline completo de exploración y evaluación paralela en 4 dimensiones."""
    pipeline = create_orchestrator_pipeline(
        web_explorer_url=web_explorer_url,
        evaluator_urls=evaluator_urls,
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
        agent=pipeline,
        session_service=session_service,
        memory_service=InMemoryMemoryService(),
        artifact_service=InMemoryArtifactService(),
        credential_service=InMemoryCredentialService(),
    )

    logger.info(f"Iniciando evaluación completa orquestada para {request.target_url} (Eval ID: {request.evaluation_id})")

    user_content = genai_types.Content(
        parts=[genai_types.Part.from_text(text=f"Iniciar auditoría heurística completa para {request.target_url}")]
    )

    async for event in runner.run_async(
        session_id=session.id,
        user_id="dima_user",
        new_message=user_content,
    ):
        pass

    final_session = await session_service.get_session(
        app_name="orchestrator",
        user_id="dima_user",
        session_id=session.id,
    )
    final_state = final_session.state if final_session else {}

    # Extraer hallazgos recolectados por los 4 evaluadores concurrentes
    findings_by_dim = {
        "dialogue": final_state.get("findings_dialogue", []),
        "action": final_state.get("findings_action", []),
        "structure": final_state.get("findings_structure", []),
        "protection": final_state.get("findings_protection", []),
    }
    all_raw_findings: List[Dict[str, Any]] = []
    for flist in findings_by_dim.values():
        all_raw_findings.extend(flist)

    validation = final_state.get("evidence_validation", {})
    exploration = final_state.get("exploration_result")

    return {
        "evaluation_id": request.evaluation_id,
        "is_valid": validation.get("valid", False),
        "validation_details": validation.get("details") or validation.get("reason"),
        "exploration_result": exploration,
        "findings_by_dimension": findings_by_dim,
        "all_raw_findings": all_raw_findings,
        "total_raw_findings": len(all_raw_findings),
        "session_state": final_state,
    }
