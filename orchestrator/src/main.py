"""Servicio FastAPI del Nodo 0 (Orquestador) con exposición A2A.

Proporciona el endpoint oficial /.well-known/agent-card.json,
el manejador de mensajes JSON-RPC 2.0 y el disparador de evaluaciones completas.
"""

import logging
import os
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from shared.schemas.evaluation import EvaluationRequest
from orchestrator.src.agent import execute_orchestrated_exploration, DEFAULT_EVIDENCE_DIR
from orchestrator.src.remote_nodes import DEFAULT_WEB_EXPLORER_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("orchestrator.main")

SERVICE_HOST = os.getenv("A2A_HOST", "orchestrator")
SERVICE_PORT = int(os.getenv("A2A_PORT", "8000"))

app = FastAPI(
    title="DIMA-HE Node 0: Orchestrator",
    description="Microservicio Orquestador A2A para la evaluación heurística automatizada de interfaces web.",
    version="1.0.0",
)


def get_agent_card() -> Dict[str, Any]:
    """Genera la Agent Card oficial compatible con la especificación A2A."""
    return {
        "name": "orchestrator",
        "description": "Orquestador del sistema distribuido DIMA-HE. Coordina el ciclo de exploración determinista con LoopAgent y EscalationChecker, dispara evaluadores paralelos y consolida reportes.",
        "version": "1.0.0",
        "url": f"http://{SERVICE_HOST}:{SERVICE_PORT}/",
        "protocol_binding": "JSONRPC",
        "skills": [
            {
                "id": "evaluate_interface",
                "name": "Evaluación Heurística de Interfaz Web",
                "description": "Ejecuta el pipeline completo de auditoría de usabilidad basado en las 10 heurísticas de Nielsen sobre la URL objetivo.",
                "input_schema": EvaluationRequest.model_json_schema(),
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "evaluation_id": {"type": "string"},
                        "is_valid": {"type": "boolean"},
                        "validation_details": {"type": "string"},
                    },
                },
            }
        ],
        "capabilities": {
            "streaming": False,
            "push_notifications": False,
        },
        "provider": {
            "organization": "DIMA-HE - Universidad Tecnológica de la Mixteca",
            "url": "https://github.com/DaveCuc/dima-he",
        },
        "default_input_modes": ["application/json"],
        "default_output_modes": ["application/json"],
    }


@app.get("/.well-known/agent-card.json", tags=["A2A Discovery"])
async def serve_agent_card() -> Dict[str, Any]:
    """Endpoint oficial de descubrimiento de tarjeta de agente (A2A Discovery)."""
    return get_agent_card()


@app.get("/health", tags=["Health"])
async def health_check() -> Dict[str, Any]:
    """Verifica el estado operativo del microservicio Orquestador."""
    return {
        "status": "healthy",
        "node_id": "node_0_orchestrator",
        "version": "1.0.0",
        "evidence_dir": DEFAULT_EVIDENCE_DIR,
        "web_explorer_url": DEFAULT_WEB_EXPLORER_URL,
    }


@app.post("/evaluate", tags=["Evaluation"])
async def evaluate_endpoint(request: EvaluationRequest) -> Dict[str, Any]:
    """Dispara directamente el ciclo orquestado de evaluación heurística."""
    logger.info(f"Orquestador: Recibida solicitud para auditar {request.target_url} (Eval ID: {request.evaluation_id})")
    try:
        result = await execute_orchestrated_exploration(
            request=request,
            web_explorer_url=DEFAULT_WEB_EXPLORER_URL,
            base_evidence_dir=DEFAULT_EVIDENCE_DIR,
        )
        return {
            "status": "success" if result["is_valid"] else "incomplete",
            "data": result,
        }
    except Exception as e:
        logger.error(f"Error en ciclo de orquestación: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fallo en la orquestación: {str(e)}",
        )


@app.post("/", tags=["A2A JSON-RPC"])
@app.post("/rpc", tags=["A2A JSON-RPC"])
@app.post("/a2a/v1/message", tags=["A2A JSON-RPC"])
async def handle_a2a_rpc(request_payload: Dict[str, Any]) -> JSONResponse:
    """Manejador oficial de mensajes JSON-RPC 2.0 del protocolo A2A para el Orquestador."""
    msg_id = request_payload.get("id")
    method = request_payload.get("method", "")
    params = request_payload.get("params", {})

    if not msg_id or not method:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32600, "message": "Petición JSON-RPC inválida: se requieren 'id' y 'method'."},
            },
        )

    if method in ["message/send", "tasks/send", "evaluate"]:
        try:
            raw_eval_req: Optional[Dict[str, Any]] = None
            if "message" in params and isinstance(params["message"], dict):
                parts = params["message"].get("parts", [])
                for part in parts:
                    if "data" in part and isinstance(part["data"], dict):
                        raw_eval_req = part["data"]
                        break
            elif "data" in params and isinstance(params["data"], dict):
                raw_eval_req = params["data"]
            elif "evaluation_id" in params and "target_url" in params:
                raw_eval_req = params

            if not raw_eval_req:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {
                            "code": -32602,
                            "message": "Parámetros inválidos: no se encontró payload válido de EvaluationRequest.",
                        },
                    },
                )

            eval_req = EvaluationRequest.model_validate(raw_eval_req)
            result = await execute_orchestrated_exploration(
                request=eval_req,
                web_explorer_url=DEFAULT_WEB_EXPLORER_URL,
                base_evidence_dir=DEFAULT_EVIDENCE_DIR,
            )

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "status": "completed" if result["is_valid"] else "incomplete",
                        "evaluation_id": eval_req.evaluation_id,
                        "is_valid": result["is_valid"],
                        "validation_details": result["validation_details"],
                        "exploration_result": result["exploration_result"],
                    },
                },
            )

        except ValidationError as ve:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32602, "message": f"Contrato de entrada inválido: {ve.errors()}"},
                },
            )
        except Exception as e:
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32603, "message": f"Error interno en orquestador: {str(e)}"},
                },
            )

    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Método '{method}' no soportado por orchestrator."},
        },
    )
