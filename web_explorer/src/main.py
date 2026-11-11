"""Servicio FastAPI del Nodo 1 (Web Explorer) con exposición A2A.

Proporciona el endpoint oficial /.well-known/agent-card.json,
el manejador de mensajes JSON-RPC 2.0 del protocolo A2A y endpoints
estructurados de exploración y healthcheck.
"""

import logging
import os
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from shared.schemas.evaluation import EvaluationRequest
from shared.schemas.exploration import ExplorationResult
from web_explorer.src.agent import execute_web_exploration
from web_explorer.src.mcp_client import PlaywrightMcpClientAsync

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("web_explorer.main")

# Determinar directorio base de evidencias según entorno (Docker vs Host)
DEFAULT_EVIDENCE_DIR = os.getenv("EVIDENCE_DIR", "/app/evidence" if os.path.exists("/app/evidence") else "evidence")
DEFAULT_MCP_URL = os.getenv("PLAYWRIGHT_MCP_URL", "http://playwright-mcp:8931/sse" if os.path.exists("/app/evidence") else "http://localhost:8931/sse")
SERVICE_HOST = os.getenv("A2A_HOST", "web-explorer")
SERVICE_PORT = int(os.getenv("A2A_PORT", "8001"))

app = FastAPI(
    title="DIMA-HE Node 1: Web Explorer",
    description="Microservicio A2A de exploración web y extracción de evidencias para evaluación heurística.",
    version="1.0.0",
)


def get_agent_card() -> Dict[str, Any]:
    """Genera la Agent Card oficial compatible con la especificación A2A."""
    return {
        "name": "web_explorer",
        "description": "Agente especializado en exploración multimodal y extracción de evidencia física (screenshots, accesibilidad, DOM) para evaluación heurística de interfaces web.",
        "version": "1.0.0",
        "url": f"http://{SERVICE_HOST}:{SERVICE_PORT}/",
        "protocol_binding": "JSONRPC",
        "skills": [
            {
                "id": "explore_web_interface",
                "name": "Exploración de Interfaz Web",
                "description": "Navega determinísticamente una URL objetivo, interactúa de forma segura con componentes y persiste capturas, árbol de accesibilidad y DOM en /app/evidence.",
                "input_schema": EvaluationRequest.model_json_schema(),
                "output_schema": ExplorationResult.model_json_schema(),
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
    """Verifica el estado operativo del microservicio y sus dependencias."""
    return {
        "status": "healthy",
        "node_id": "node_1_web_explorer",
        "version": "1.0.0",
        "evidence_dir": DEFAULT_EVIDENCE_DIR,
        "mcp_url": DEFAULT_MCP_URL,
    }


@app.post("/explore", response_model=ExplorationResult, tags=["Exploration"])
async def explore_endpoint(request: EvaluationRequest) -> ExplorationResult:
    """Endpoint directo estructurado para ejecutar la exploración de interfaz web."""
    logger.info(f"Recibida solicitud de exploración para {request.target_url} (Eval ID: {request.evaluation_id})")
    try:
        mcp_client = PlaywrightMcpClientAsync(base_url=DEFAULT_MCP_URL)
        result = await execute_web_exploration(
            request=request,
            base_evidence_dir=DEFAULT_EVIDENCE_DIR,
            mcp_client=mcp_client,
        )
        return result
    except Exception as e:
        logger.error(f"Error durante la exploración web: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error durante la exploración: {str(e)}",
        )


@app.post("/", tags=["A2A JSON-RPC"])
@app.post("/rpc", tags=["A2A JSON-RPC"])
@app.post("/a2a/v1/message", tags=["A2A JSON-RPC"])
async def handle_a2a_rpc(request_payload: Dict[str, Any]) -> JSONResponse:
    """Manejador oficial de mensajes JSON-RPC 2.0 del protocolo A2A."""
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

    # Métodos soportados por el Web Explorer
    if method in ["message/send", "tasks/send", "explore"]:
        try:
            # Extraer payload según estructura A2A
            raw_eval_req: Optional[Dict[str, Any]] = None
            if "message" in params and isinstance(params["message"], dict):
                # Formato A2A estándar: { message: { parts: [ { data: { ... } } ] } }
                parts = params["message"].get("parts", [])
                for part in parts:
                    if "data" in part and isinstance(part["data"], dict):
                        raw_eval_req = part["data"]
                        break
            elif "data" in params and isinstance(params["data"], dict):
                raw_eval_req = params["data"]
            elif "evaluation_id" in params and "target_url" in params:
                raw_eval_req = params
            elif "request" in params and isinstance(params["request"], dict):
                raw_eval_req = params["request"]

            if not raw_eval_req:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {
                            "code": -32602,
                            "message": "Parámetros inválidos: no se encontró payload válido de EvaluationRequest en 'params'.",
                        },
                    },
                )

            # Validar contrato Pydantic v2
            eval_request = EvaluationRequest.model_validate(raw_eval_req)

            mcp_client = PlaywrightMcpClientAsync(base_url=DEFAULT_MCP_URL)
            exploration_result = await execute_web_exploration(
                request=eval_request,
                base_evidence_dir=DEFAULT_EVIDENCE_DIR,
                mcp_client=mcp_client,
            )

            # Devolver respuesta JSON-RPC 2.0 con el contrato ExplorationResult
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "status": "completed",
                        "exploration": exploration_result.model_dump(mode="json"),
                    },
                },
            )

        except ValidationError as ve:
            logger.error(f"Error de validación Pydantic: {ve}")
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32602,
                        "message": f"Contrato de entrada inválido: {ve.errors()}",
                    },
                },
            )
        except Exception as e:
            logger.error(f"Error interno procesando A2A RPC: {e}", exc_info=True)
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32603,
                        "message": f"Error interno en ejecución de explorador: {str(e)}",
                    },
                },
            )

    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Método '{method}' no encontrado en web_explorer."},
        },
    )
