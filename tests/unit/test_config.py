"""Pruebas unitarias para validar la integridad de los archivos de configuración YAML."""

from pathlib import Path
from shared.enums.heuristics import HeuristicId, EvaluatorDimension, DIMENSION_HEURISTICS
from shared.utils.yaml_loader import (
    get_heuristics_config,
    get_agents_config,
    get_evaluation_config,
)


class TestConfigIntegrity:
    """Valida la consistencia de los archivos YAML de configuración."""

    def test_heuristics_yaml_contains_all_ten_heuristics(self):
        config = get_heuristics_config()
        heuristics = config.get("heuristics", {})
        assert len(heuristics) == 10

        # Verificar que existan exactamente de H1 a H10
        for h_id in [f"H{i}" for i in range(1, 11)]:
            assert h_id in heuristics
            h_data = heuristics[h_id]
            assert "name" in h_data
            assert "dimension" in h_data
            assert "description" in h_data
            assert "evaluation_checklist" in h_data
            assert len(h_data["evaluation_checklist"]) > 0

    def test_heuristics_dimensions_assignment(self):
        config = get_heuristics_config()
        dimensions = config.get("dimensions", {})
        assert len(dimensions) == 4

        # Verificar correspondencia exacta con las 4 dimensiones
        expected_dims = {
            "dialogue": ["H1", "H2", "H10"],
            "action": ["H3", "H7"],
            "structure": ["H4", "H6", "H8"],
            "protection": ["H5", "H9"],
        }
        for dim, expected_heuristics in expected_dims.items():
            assert dim in dimensions
            assigned = dimensions[dim]["heuristics"]
            assert sorted(assigned) == sorted(expected_heuristics)

    def test_severities_scale_zero_to_four(self):
        config = get_heuristics_config()
        severities = config.get("severities", {})
        assert len(severities) == 5
        for level in range(5):
            assert level in severities
            assert "name" in severities[level]
            assert "description" in severities[level]

    def test_agents_yaml_contains_seven_nodes(self):
        config = get_agents_config()
        services = config.get("services", {})
        # N0 a N6: 7 servicios de agentes
        assert len(services) == 7

        expected_nodes = [
            "orchestrator",
            "web_explorer",
            "evaluator_dialogue",
            "evaluator_action",
            "evaluator_structure",
            "evaluator_protection",
            "report_creator",
        ]
        for node in expected_nodes:
            assert node in services
            assert "internal_port" in services[node]
            assert "agent_card_url" in services[node]
            assert "evidence_access" in services[node]

        # Verificar el servicio de infraestructura Playwright MCP
        infra = config.get("infrastructure", {})
        assert "playwright_mcp" in infra
        assert infra["playwright_mcp"]["internal_port"] == 8931
        assert infra["playwright_mcp"]["shm_size"] == "1gb"

    def test_evaluation_yaml_timeouts_and_depth(self):
        config = get_evaluation_config()
        timeouts = config.get("timeouts", {})
        assert timeouts.get("page_load_seconds") == 30
        assert timeouts.get("interaction_seconds") == 60

        exploration = config.get("exploration", {})
        assert exploration.get("max_depth") == 1
        assert exploration.get("max_iterations") == 3
        assert exploration.get("allow_destructive_actions") is False
