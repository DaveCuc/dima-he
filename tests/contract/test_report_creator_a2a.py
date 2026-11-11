"""Pruebas de contrato A2A para el Nodo 6 (Report Creator)."""

import pytest
from fastapi.testclient import TestClient
from report_creator.src.main import app
from shared.enums.agent_role import EvaluatorAgentId
from shared.enums.heuristics import HeuristicId
from shared.schemas.finding import ConsolidatedFinding, ConsolidatedFindings, FindingLocation


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_consolidated():
    cf = ConsolidatedFinding(
        finding_id="cons-find-001",
        evaluation_id="eval-a2a-rep-001",
        agent_id=EvaluatorAgentId.DIALOGUE,
        problem="Problema de prueba A2A",
        heuristic_id=HeuristicId.H1,
        heuristic_name="Visibilidad del estado del sistema",
        justification="Justificación técnica de prueba",
        location=FindingLocation(page="home", element="header", selector="header.nav"),
        evidence_ids=[],
        severity=2,
        severity_justification="Severidad moderada",
        improvement="Mejora sugerida",
        confidence=0.90,
        source_agents=[EvaluatorAgentId.DIALOGUE],
        original_finding_ids=["find-001"],
    )
    return ConsolidatedFindings(
        evaluation_id="eval-a2a-rep-001",
        findings=[cf],
        total_raw_findings=1,
        total_consolidated_findings=1,
        duplicates_removed=0,
    )


class TestReportCreatorA2AContract:
    """Valida los endpoints y contratos A2A expuestos por el Nodo 6."""

    def test_agent_card_discovery_compliance(self, client):
        response = client.get("/.well-known/agent-card.json")
        assert response.status_code == 200
        card = response.json()

        assert card["name"] == "node_6_report_creator"
        assert card["version"] == "1.0.0"
        assert card["protocol_binding"] == "JSONRPC"
        assert len(card["skills"]) >= 1

        skill = card["skills"][0]
        assert skill["id"] == "generate_reports"
        assert "input_schema" in skill
        assert "output_schema" in skill

    def test_health_check_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["node_id"] == "node_6_report_creator"
        assert "json" in data["output_formats"]
        assert "md" in data["output_formats"]
        assert "csv" in data["output_formats"]

    def test_direct_generate_rest_endpoint(self, client, sample_consolidated, tmp_path, monkeypatch):
        temp_evidence = tmp_path / "evidence"
        monkeypatch.setattr("report_creator.src.main.DEFAULT_EVIDENCE_DIR", str(temp_evidence))

        payload = sample_consolidated.model_dump(mode="json")
        response = client.post("/generate", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "completed"
        assert data["evaluation_id"] == "eval-a2a-rep-001"
        assert "files" in data
        assert "statistics" in data
        assert "json" in data["files"]
        assert "markdown" in data["files"]
        assert "csv" in data["files"]

    def test_a2a_jsonrpc_message_send_flow(self, client, sample_consolidated, tmp_path, monkeypatch):
        temp_evidence = tmp_path / "evidence"
        monkeypatch.setattr("report_creator.src.main.DEFAULT_EVIDENCE_DIR", str(temp_evidence))

        rpc_request = {
            "jsonrpc": "2.0",
            "id": "test-req-001",
            "method": "message/send",
            "params": {
                "message": {
                    "parts": [
                        {
                            "data": sample_consolidated.model_dump(mode="json")
                        }
                    ]
                }
            },
        }

        response = client.post("/a2a/v1/message", json=rpc_request)
        assert response.status_code == 200
        data = response.json()

        assert data["jsonrpc"] == "2.0"
        assert data["id"] == "test-req-001"
        assert "result" in data
        result = data["result"]
        assert result["status"] == "completed"
        assert result["evaluation_id"] == "eval-a2a-rep-001"
        assert "files" in result
        assert "statistics" in result

    def test_a2a_jsonrpc_unsupported_method(self, client):
        rpc_request = {
            "jsonrpc": "2.0",
            "id": "test-err-001",
            "method": "unknown_action",
            "params": {},
        }
        response = client.post("/a2a/v1/message", json=rpc_request)
        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == -32601

    def test_a2a_jsonrpc_invalid_payload_error(self, client):
        rpc_request = {
            "jsonrpc": "2.0",
            "id": "test-err-002",
            "method": "message/send",
            "params": {
                "message": {
                    "parts": [{"data": {"invalid_key": "bad_data"}}]
                }
            },
        }
        response = client.post("/a2a/v1/message", json=rpc_request)
        assert response.status_code == 422
        data = response.json()
        assert data["error"]["code"] == -32602
