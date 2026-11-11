"""Pruebas de contrato y endpoints A2A para el Nodo 1 (Web Explorer) - Fase 4."""

import pytest
from fastapi.testclient import TestClient
from shared.schemas.evaluation import EvaluationRequest, EvaluationScope
from web_explorer.src.main import app

client = TestClient(app)


class TestWebExplorerA2AContract:
    """Valida los criterios de aceptación de Fase 4 para la exposición A2A del Nodo 1."""

    def test_health_check_endpoint(self):
        """Verifica que el endpoint /health responda correctamente."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["node_id"] == "node_1_web_explorer"
        assert "evidence_dir" in data

    def test_agent_card_discovery_well_known(self):
        """Criterio de aceptación principal de Fase 4:
        GET /.well-known/agent-card.json debe cumplir con el estándar A2A.
        """
        response = client.get("/.well-known/agent-card.json")
        assert response.status_code == 200
        card = response.json()

        # Validar campos raíz del protocolo A2A
        assert card["name"] == "web_explorer"
        assert "description" in card
        assert card["protocol_binding"] == "JSONRPC"
        assert "url" in card

        # Validar skills expuestas
        assert "skills" in card
        assert len(card["skills"]) >= 1
        skill = card["skills"][0]
        assert skill["id"] == "explore_web_interface"
        assert "input_schema" in skill
        assert "output_schema" in skill

        # Validar que los esquemas JSON correspondan a los contratos Pydantic v2
        assert "EvaluationRequest" in skill["input_schema"]["title"]
        assert "ExplorationResult" in skill["output_schema"]["title"]

        # Validar capabilities y provider
        assert "capabilities" in card
        assert "provider" in card

    def test_a2a_rpc_invalid_payload_handling(self):
        """Verifica que peticiones malformadas reciban errores estándar JSON-RPC."""
        # 1. Petición sin id ni method
        res1 = client.post("/", json={"foo": "bar"})
        assert res1.status_code == 400
        data1 = res1.json()
        assert data1["jsonrpc"] == "2.0"
        assert data1["error"]["code"] == -32600

        # 2. Método desconocido
        res2 = client.post("/", json={"jsonrpc": "2.0", "id": 10, "method": "unknown_action"})
        assert res2.status_code == 404
        data2 = res2.json()
        assert data2["error"]["code"] == -32601

        # 3. Método válido pero sin payload de EvaluationRequest
        res3 = client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "id": 11,
                "method": "message/send",
                "params": {"message": {"parts": []}},
            },
        )
        assert res3.status_code == 400
        data3 = res3.json()
        assert data3["error"]["code"] == -32602

    def test_a2a_rpc_schema_validation_error(self):
        """Verifica que esquemas de entrada inválidos devuelvan error de validación."""
        res = client.post(
            "/a2a/v1/message",
            json={
                "jsonrpc": "2.0",
                "id": 12,
                "method": "message/send",
                "params": {
                    "data": {
                        "evaluation_id": "invalid ID with spaces!",
                        "target_url": "ftp://not-supported.org",
                    }
                },
            },
        )
        assert res.status_code == 422
        data = res.json()
        assert data["error"]["code"] == -32602
        assert "Contrato de entrada inválido" in data["error"]["message"]

    def test_a2a_rpc_full_exploration_flow(self):
        """Ejecuta una llamada completa A2A JSON-RPC 2.0 y valida la respuesta del contrato."""
        eval_id = "eval-phase4-contract"
        eval_request_dict = {
            "evaluation_id": eval_id,
            "target_url": "https://example.com",
            "scope": {"max_depth": 0},
            "instructions": "Prueba de contrato A2A para Fase 4.",
        }

        rpc_request = {
            "jsonrpc": "2.0",
            "id": 42,
            "method": "message/send",
            "params": {
                "message": {
                    "parts": [
                        {
                            "data": eval_request_dict,
                        }
                    ]
                }
            },
        }

        response = client.post("/a2a/v1/message", json=rpc_request)
        assert response.status_code == 200
        res_data = response.json()

        assert res_data["jsonrpc"] == "2.0"
        assert res_data["id"] == 42
        assert "result" in res_data
        result_payload = res_data["result"]
        assert result_payload["status"] == "completed"

        # Validar el contrato ExplorationResult devuelto
        exploration = result_payload["exploration"]
        assert exploration["evaluation_id"] == eval_id
        assert exploration["total_pages"] == 1
        assert len(exploration["pages_explored"]) == 1

        page = exploration["pages_explored"][0]
        assert "example" in page["url"]
        assert page["accessibility_snapshot_path"] is not None
        assert page["dom_reference_path"] is not None
        assert len(page["screenshots"]) >= 1
