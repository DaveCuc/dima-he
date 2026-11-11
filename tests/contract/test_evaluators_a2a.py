"""Pruebas de contrato A2A para los cuatro microservicios evaluadores (Fase 6)."""

import pytest
from fastapi.testclient import TestClient
from evaluators.dialogue.src.main import app as dialogue_app
from evaluators.action.src.main import app as action_app
from evaluators.structure.src.main import app as structure_app
from evaluators.protection.src.main import app as protection_app
from shared.schemas.exploration import ExplorationResult, PageExplorationResult


@pytest.fixture
def sample_exploration_payload():
    return {
        "evaluation_id": "eval-contract-test",
        "target_url": "https://example.com",
        "total_pages": 1,
        "total_screenshots": 0,
        "pages_explored": [
            {
                "evaluation_id": "eval-contract-test",
                "page_id": "page_01_home",
                "url": "https://example.com",
                "title": "Example Domain",
                "screenshots": [],
                "actions_performed": ["Navegar a https://example.com"],
            }
        ],
    }


class TestEvaluatorsA2AContract:
    """Valida los contratos y especificación A2A de los 4 evaluadores."""

    @pytest.mark.parametrize(
        "app_instance, expected_node, expected_dim",
        [
            (dialogue_app, "evaluator_dialogue", "dialogue"),
            (action_app, "evaluator_action", "action"),
            (structure_app, "evaluator_structure", "structure"),
            (protection_app, "evaluator_protection", "protection"),
        ],
    )
    def test_agent_card_structure(self, app_instance, expected_node, expected_dim):
        """Verifica que cada evaluador exponga una Agent Card válida según la especificación A2A."""
        client = TestClient(app_instance)
        response = client.get("/.well-known/agent-card.json")
        assert response.status_code == 200
        card = response.json()

        assert card["name"] == expected_node
        assert card["protocol_binding"] == "JSONRPC"
        assert "skills" in card
        assert len(card["skills"]) == 1

        skill = card["skills"][0]
        assert skill["id"] == f"evaluate_{expected_dim}"
        assert "ExplorationResult" in skill["input_schema"]["title"]
        assert "EvaluatorFindingList" in skill["output_schema"]["title"]

    @pytest.mark.parametrize(
        "app_instance, expected_node",
        [
            (dialogue_app, "evaluator_dialogue"),
            (action_app, "evaluator_action"),
            (structure_app, "evaluator_structure"),
            (protection_app, "evaluator_protection"),
        ],
    )
    def test_evaluator_healthcheck(self, app_instance, expected_node):
        """Verifica que los cuatro evaluadores respondan correctamente a /health."""
        client = TestClient(app_instance)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["node_id"] == expected_node

    @pytest.mark.parametrize("app_instance", [dialogue_app, action_app, structure_app, protection_app])
    def test_a2a_rpc_invalid_payload_error(self, app_instance):
        """Verifica que solicitudes RPC malformadas reciban errores -32600 y -32602."""
        client = TestClient(app_instance)
        # Sin id ni method
        res1 = client.post("/", json={"foo": "bar"})
        assert res1.status_code == 400
        assert res1.json()["error"]["code"] == -32600

        # Método inexistente
        res2 = client.post("/", json={"jsonrpc": "2.0", "id": 1, "method": "unknown_action"})
        assert res2.status_code == 404
        assert res2.json()["error"]["code"] == -32601

    @pytest.mark.parametrize(
        "app_instance, expected_dim",
        [
            (dialogue_app, "dialogue"),
            (action_app, "action"),
            (structure_app, "structure"),
            (protection_app, "protection"),
        ],
    )
    def test_a2a_rpc_evaluation_message_flow(self, app_instance, expected_dim, sample_exploration_payload):
        """Verifica el flujo estándar A2A JSON-RPC 2.0 (message/send) retornando hallazgos tipados."""
        client = TestClient(app_instance)
        rpc_request = {
            "jsonrpc": "2.0",
            "id": 100,
            "method": "message/send",
            "params": {
                "message": {
                    "parts": [
                        {
                            "data": sample_exploration_payload,
                        }
                    ]
                }
            },
        }

        response = client.post("/a2a/v1/message", json=rpc_request)
        assert response.status_code == 200
        res_data = response.json()

        assert res_data["jsonrpc"] == "2.0"
        assert res_data["id"] == 100
        assert "result" in res_data
        result_payload = res_data["result"]
        assert result_payload["status"] == "completed"
        assert result_payload["dimension"] == expected_dim
        assert "findings" in result_payload
        assert isinstance(result_payload["findings"], list)
