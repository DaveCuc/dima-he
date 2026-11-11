"""Microservicio FastAPI del Nodo 2 (Evaluador de Diálogo) con exposición A2A."""

import logging
import os
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from shared.schemas.exploration import ExplorationResult
from shared.schemas.finding import EvaluatorFindingList
from evaluators.dialogue.src.agent import create_dialogue_evaluator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("evaluator.dialogue")

evaluator = create_dialogue_evaluator()
DEFAULT_EVIDENCE_DIR = os.getenv("EVIDENCE_DIR", "/app/evidence" if os.path.exists("/app/evidence") else "evidence")

app = FastAPI(
    title="DIMA-HE Node 2: Evaluator Dialogue",
    description="Microservicio A2A para evaluación heurística de Diálogo, Visibilidad y Ayuda (H1, H2, H10).",
    version="1.0.0",
)


@app.get("/.well-known/agent-card.json", tags=["A2A Discovery"])
async def serve_agent_card() -> Dict[str, Any]:
    return evaluator.get_agent_card()


@app.get("/health", tags=["Health"])
async def health_check() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "node_id": evaluator.node_id.value,
        "dimension": evaluator.dimension,
        "heuristics": evaluator.heuristics,
    }


@app.post("/evaluate", response_model=EvaluatorFindingList, tags=["Evaluation"])
async def evaluate_endpoint(exploration: ExplorationResult) -> EvaluatorFindingList:
    try:
        return await evaluator.evaluate(exploration, base_evidence_dir=DEFAULT_EVIDENCE_DIR)
    except Exception as e:
        logger.error(f"Error en evaluación de diálogo: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/", tags=["A2A JSON-RPC"])
@app.post("/rpc", tags=["A2A JSON-RPC"])
@app.post("/a2a/v1/message", tags=["A2A JSON-RPC"])
async def handle_a2a_rpc(request_payload: Dict[str, Any]) -> JSONResponse:
    msg_id = request_payload.get("id")
    method = request_payload.get("method", "")
    params = request_payload.get("params", {})

    if not msg_id or not method:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32600, "message": "Petición JSON-RPC inválida."}},
        )

    if method in ["message/send", "tasks/send", "evaluate"]:
        try:
            raw_data = None
            if "message" in params and isinstance(params["message"], dict):
                parts = params["message"].get("parts", [])
                for part in parts:
                    if "data" in part and isinstance(part["data"], dict):
                        raw_data = part["data"]
                        break
            elif "data" in params and isinstance(params["data"], dict):
                raw_data = params["data"]
            elif "pages_explored" in params:
                raw_data = params

            if not raw_data:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32602, "message": "Falta payload de ExplorationResult."}},
                )

            exploration_result = ExplorationResult.model_validate(raw_data)
            findings_list = await evaluator.evaluate(exploration_result, base_evidence_dir=DEFAULT_EVIDENCE_DIR)

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "status": "completed",
                        "dimension": evaluator.dimension,
                        "findings": findings_list.model_dump(mode="json")["findings"],
                    },
                },
            )
        except ValidationError as ve:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32602, "message": f"Contrato inválido: {ve.errors()}"}},
            )
        except Exception as e:
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32603, "message": str(e)}},
            )

    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"Método '{method}' no soportado."}},
    )
