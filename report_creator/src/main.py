"""Microservicio FastAPI del Nodo 6 (Report Creator) con exposición A2A."""

import logging
import os
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from shared.schemas.finding import ConsolidatedFindings
from report_creator.src.agent import create_report_creator_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("report_creator.main")

DEFAULT_EVIDENCE_DIR = os.getenv("EVIDENCE_DIR", "/app/evidence" if os.path.exists("/app/evidence") else "evidence")
agent = create_report_creator_agent(base_evidence_dir=DEFAULT_EVIDENCE_DIR)

app = FastAPI(
    title="DIMA-HE Node 6: Report Creator",
    description="Microservicio A2A para consolidación de métricas y generación física de reportes (results.json, report.md, report.csv).",
    version="1.0.0",
)


@app.get("/.well-known/agent-card.json", tags=["A2A Discovery"])
async def serve_agent_card() -> Dict[str, Any]:
    return agent.get_agent_card()


@app.get("/health", tags=["Health"])
async def health_check() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "node_id": agent.node_id,
        "output_formats": ["json", "md", "csv"],
        "base_evidence_dir": str(agent.base_evidence_dir),
    }


@app.post("/generate", tags=["Reports"])
@app.post("/report", tags=["Reports"])
async def generate_endpoint(payload: ConsolidatedFindings) -> Dict[str, Any]:
    try:
        result = agent.generate_reports(payload, base_evidence_dir=DEFAULT_EVIDENCE_DIR)
        return {
            "status": "completed",
            "evaluation_id": result["evaluation_id"],
            "statistics": result["statistics"],
            "files": result["files"],
        }
    except Exception as e:
        logger.error(f"Error generando reportes: {e}", exc_info=True)
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

    if method in ["message/send", "tasks/send", "generate", "create_report"]:
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
            elif "findings" in params and "evaluation_id" in params:
                raw_data = params

            if not raw_data:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32602, "message": "Falta payload de ConsolidatedFindings."}},
                )

            consolidated = ConsolidatedFindings.model_validate(raw_data)
            gen_result = agent.generate_reports(consolidated, base_evidence_dir=DEFAULT_EVIDENCE_DIR)

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "status": "completed",
                        "evaluation_id": gen_result["evaluation_id"],
                        "statistics": gen_result["statistics"],
                        "files": gen_result["files"],
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
