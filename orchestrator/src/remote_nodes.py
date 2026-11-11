"""Agente cliente A2A para interactuar con el Nodo 1 (Web Explorer).

Permite al Orquestador (Nodo 0) invocar de forma remota y desacoplada
al microservicio de exploración mediante el protocolo estándar A2A JSON-RPC 2.0.
"""

import logging
import os
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types as genai_types

from shared.schemas.evaluation import EvaluationRequest
from shared.schemas.exploration import ExplorationResult
from shared.schemas.finding import EvaluatorFindingList

logger = logging.getLogger(__name__)

DEFAULT_WEB_EXPLORER_URL = os.getenv(
    "WEB_EXPLORER_URL",
    "http://web-explorer:8001/a2a/v1/message" if os.path.exists("/app/evidence") else "http://localhost:8001/a2a/v1/message"
)

IS_CONTAINER = os.path.exists("/app/evidence")

DEFAULT_EVALUATOR_URLS = {
    "dialogue": os.getenv("EVALUATOR_DIALOGUE_URL", "http://evaluator-dialogue:8002/a2a/v1/message" if IS_CONTAINER else "http://localhost:8002/a2a/v1/message"),
    "action": os.getenv("EVALUATOR_ACTION_URL", "http://evaluator-action:8003/a2a/v1/message" if IS_CONTAINER else "http://localhost:8003/a2a/v1/message"),
    "structure": os.getenv("EVALUATOR_STRUCTURE_URL", "http://evaluator-structure:8004/a2a/v1/message" if IS_CONTAINER else "http://localhost:8004/a2a/v1/message"),
    "protection": os.getenv("EVALUATOR_PROTECTION_URL", "http://evaluator-protection:8005/a2a/v1/message" if IS_CONTAINER else "http://localhost:8005/a2a/v1/message"),
}

DEFAULT_REPORT_CREATOR_URL = os.getenv(
    "REPORT_CREATOR_URL",
    "http://report-creator:8006/a2a/v1/message" if IS_CONTAINER else "http://localhost:8006/a2a/v1/message"
)


class RemoteWebExplorerAgent(BaseAgent):
    """Invoca remotamente al Nodo 1 (Web Explorer) a través de A2A HTTP JSON-RPC 2.0."""

    endpoint_url: str = DEFAULT_WEB_EXPLORER_URL
    timeout: float = 120.0

    def __init__(
        self,
        name: str = "remote_web_explorer",
        endpoint_url: str = DEFAULT_WEB_EXPLORER_URL,
        timeout: float = 120.0,
        **kwargs,
    ):
        super().__init__(
            name=name,
            description="Invoca al Nodo 1 para explorar la web y recopilar evidencia física mediante A2A.",
            **kwargs,
        )
        self.endpoint_url = endpoint_url
        self.timeout = timeout

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """Ejecuta la llamada A2A hacia el microservicio Web Explorer."""
        state = ctx.session.state if ctx.session else {}
        req_data = state.get("evaluation_request")

        if not req_data:
            err_msg = "RemoteWebExplorerAgent: No se encontró 'evaluation_request' en el estado de sesión."
            logger.error(err_msg)
            yield Event(
                author=self.name,
                content=genai_types.Content(parts=[genai_types.Part.from_text(text=err_msg)]),
                actions=EventActions(escalate=False),
            )
            return

        # Asegurar instancia de EvaluationRequest
        if isinstance(req_data, dict):
            eval_req = EvaluationRequest.model_validate(req_data)
        elif isinstance(req_data, EvaluationRequest):
            eval_req = req_data
        else:
            eval_req = EvaluationRequest.model_validate(req_data)

        # Si hubo retroalimentación de una iteración anterior, enriquecer instrucciones
        feedback = state.get("exploration_feedback")
        if feedback:
            logger.info(f"Aplicando feedback de iteración previa en exploración: {feedback}")
            eval_req = eval_req.model_copy(
                update={"instructions": f"{eval_req.instructions or ''} [Retroalimentación: {feedback}]".strip()}
            )

        # Construir paquete A2A JSON-RPC 2.0
        rpc_payload = {
            "jsonrpc": "2.0",
            "id": f"a2a-exp-{eval_req.evaluation_id}",
            "method": "message/send",
            "params": {
                "message": {
                    "parts": [
                        {
                            "data": eval_req.model_dump(mode="json"),
                        }
                    ]
                }
            },
        }

        logger.info(f"Invocando Web Explorer A2A en {self.endpoint_url} para {eval_req.target_url}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.endpoint_url, json=rpc_payload)
                response.raise_for_status()
                res_json = response.json()

            if "error" in res_json:
                error_info = res_json["error"]
                err_desc = f"Error devuelto por Web Explorer A2A: {error_info}"
                logger.error(err_desc)
                state["exploration_feedback"] = err_desc
                yield Event(
                    author=self.name,
                    content=genai_types.Content(parts=[genai_types.Part.from_text(text=err_desc)]),
                    actions=EventActions(escalate=False),
                )
                return

            result_data = res_json.get("result", {})
            exploration_dict = result_data.get("exploration")
            if not exploration_dict:
                err_desc = "Web Explorer A2A no retornó el bloque 'exploration' en el resultado."
                logger.error(err_desc)
                state["exploration_feedback"] = err_desc
                yield Event(
                    author=self.name,
                    content=genai_types.Content(parts=[genai_types.Part.from_text(text=err_desc)]),
                    actions=EventActions(escalate=False),
                )
                return

            # Validar y almacenar ExplorationResult en el estado de sesión
            exploration_result = ExplorationResult.model_validate(exploration_dict)
            state["exploration_result"] = exploration_result.model_dump(mode="json")
            state["total_pages_explored"] = exploration_result.total_pages

            success_msg = f"Exploración A2A completada exitosamente. Páginas exploradas: {exploration_result.total_pages}"
            logger.info(success_msg)

            yield Event(
                author=self.name,
                content=genai_types.Content(parts=[genai_types.Part.from_text(text=success_msg)]),
                actions=EventActions(
                    escalate=False,
                    state_delta={
                        "exploration_result": exploration_result.model_dump(mode="json"),
                        "total_pages_explored": exploration_result.total_pages,
                    },
                ),
            )

        except Exception as e:
            err_desc = f"Fallo de comunicación HTTP A2A con Web Explorer ({self.endpoint_url}): {str(e)}"
            logger.error(err_desc, exc_info=True)
            state["exploration_feedback"] = err_desc
            yield Event(
                author=self.name,
                content=genai_types.Content(parts=[genai_types.Part.from_text(text=err_desc)]),
                actions=EventActions(escalate=False),
            )


class RemoteEvaluatorAgent(BaseAgent):
    """Agente cliente A2A que invoca a un microservicio evaluador heurístico."""

    dimension: str = ""
    endpoint_url: str = ""
    timeout: float = 60.0

    def __init__(
        self,
        name: str,
        dimension: str,
        endpoint_url: str,
        timeout: float = 60.0,
        **kwargs,
    ):
        super().__init__(
            name=name,
            dimension=dimension,
            endpoint_url=endpoint_url,
            timeout=timeout,
            description=f"Invoca al Evaluador A2A de la dimensión '{dimension}'.",
            **kwargs,
        )

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """Envía el ExplorationResult al evaluador correspondiente y captura sus hallazgos."""
        state = ctx.session.state if ctx.session else {}
        exploration_data = state.get("exploration_result")

        if not exploration_data:
            err_msg = f"RemoteEvaluatorAgent ({self.dimension}): No hay 'exploration_result' disponible para evaluar."
            logger.error(err_msg)
            yield Event(
                author=self.name,
                content=genai_types.Content(parts=[genai_types.Part.from_text(text=err_msg)]),
                actions=EventActions(escalate=False),
            )
            return

        eval_id = exploration_data.get("evaluation_id", "unknown")
        rpc_payload = {
            "jsonrpc": "2.0",
            "id": f"a2a-eval-{self.dimension}-{eval_id}",
            "method": "message/send",
            "params": {
                "message": {
                    "parts": [
                        {
                            "data": exploration_data,
                        }
                    ]
                }
            },
        }

        logger.info(f"Invocando Evaluador A2A ({self.dimension}) en {self.endpoint_url}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.endpoint_url, json=rpc_payload)
                response.raise_for_status()
                res_json = response.json()

            if "error" in res_json:
                error_info = res_json["error"]
                err_desc = f"Error devuelto por Evaluador ({self.dimension}): {error_info}"
                logger.error(err_desc)
                yield Event(
                    author=self.name,
                    content=genai_types.Content(parts=[genai_types.Part.from_text(text=err_desc)]),
                    actions=EventActions(escalate=False),
                )
                return

            result_data = res_json.get("result", {})
            raw_findings = result_data.get("findings", [])

            findings_list = EvaluatorFindingList(findings=raw_findings)
            logger.info(f"Evaluador ({self.dimension}) identificó {len(findings_list.findings)} hallazgos.")

            yield Event(
                author=self.name,
                content=genai_types.Content(
                    parts=[genai_types.Part.from_text(text=f"Evaluación de {self.dimension} completada: {len(findings_list.findings)} hallazgos.")]
                ),
                actions=EventActions(
                    escalate=False,
                    state_delta={
                        f"findings_{self.dimension}": findings_list.model_dump(mode="json")["findings"]
                    },
                ),
            )

        except Exception as e:
            err_desc = f"Fallo al invocar Evaluador A2A ({self.dimension}) en {self.endpoint_url}: {str(e)}"
            logger.error(err_desc, exc_info=True)
            yield Event(
                author=self.name,
                content=genai_types.Content(parts=[genai_types.Part.from_text(text=err_desc)]),
                actions=EventActions(
                    escalate=False,
                    state_delta={f"findings_{self.dimension}": []},
                ),
            )


class RemoteReportCreatorAgent(BaseAgent):
    """Invoca remotamente al Nodo 6 (Report Creator) a través de A2A HTTP JSON-RPC 2.0."""

    endpoint_url: str = DEFAULT_REPORT_CREATOR_URL
    timeout: float = 60.0

    def __init__(
        self,
        name: str = "remote_report_creator",
        endpoint_url: str = DEFAULT_REPORT_CREATOR_URL,
        timeout: float = 60.0,
        **kwargs,
    ):
        super().__init__(
            name=name,
            description="Invoca al Nodo 6 para generar y persistir físicamente los reportes finales (JSON, MD, CSV) mediante A2A.",
            **kwargs,
        )
        self.endpoint_url = endpoint_url
        self.timeout = timeout

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """Envía ConsolidatedFindings al Nodo 6 y almacena las rutas de los reportes generados."""
        state = ctx.session.state if ctx.session else {}
        consolidated_data = state.get("consolidated_findings")

        if not consolidated_data:
            err_msg = "RemoteReportCreatorAgent: No se encontró 'consolidated_findings' en el estado de sesión."
            logger.error(err_msg)
            yield Event(
                author=self.name,
                content=genai_types.Content(parts=[genai_types.Part.from_text(text=err_msg)]),
                actions=EventActions(escalate=False),
            )
            return

        eval_id = consolidated_data.get("evaluation_id", state.get("evaluation_id", "unknown_eval"))
        rpc_payload = {
            "jsonrpc": "2.0",
            "id": f"a2a-rep-{eval_id}",
            "method": "message/send",
            "params": {
                "message": {
                    "parts": [
                        {
                            "data": consolidated_data,
                        }
                    ]
                }
            },
        }

        logger.info(f"Invocando Report Creator A2A en {self.endpoint_url} para auditoría [{eval_id}]")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.endpoint_url, json=rpc_payload)
                response.raise_for_status()
                res_json = response.json()

            if "error" in res_json:
                error_info = res_json["error"]
                err_desc = f"Error devuelto por Report Creator A2A: {error_info}"
                logger.error(err_desc)
                yield Event(
                    author=self.name,
                    content=genai_types.Content(parts=[genai_types.Part.from_text(text=err_desc)]),
                    actions=EventActions(escalate=False, state_delta={"report_error": err_desc}),
                )
                return

            result_data = res_json.get("result", {})
            files_dict = result_data.get("files", {})
            stats_dict = result_data.get("statistics", {})

            success_msg = (
                f"Reportes generados exitosamente por Nodo 6: "
                f"JSON={files_dict.get('json')}, MD={files_dict.get('markdown')}, CSV={files_dict.get('csv')}"
            )
            logger.info(success_msg)

            yield Event(
                author=self.name,
                content=genai_types.Content(parts=[genai_types.Part.from_text(text=success_msg)]),
                actions=EventActions(
                    escalate=False,
                    state_delta={
                        "report_files": files_dict,
                        "report_statistics": stats_dict,
                    },
                ),
            )

        except Exception as e:
            err_desc = f"Fallo al invocar Report Creator A2A ({self.endpoint_url}): {str(e)}"
            logger.error(err_desc, exc_info=True)
            yield Event(
                author=self.name,
                content=genai_types.Content(parts=[genai_types.Part.from_text(text=err_desc)]),
                actions=EventActions(escalate=False, state_delta={"report_error": err_desc}),
            )

