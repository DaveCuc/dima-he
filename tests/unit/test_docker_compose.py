"""Pruebas unitarias para validar la configuración de docker-compose.yml (Fase 8)."""

import pytest
import yaml
from pathlib import Path
from shared.utils.yaml_loader import get_agents_config

COMPOSE_FILE = Path("docker-compose.yml")


class TestDockerComposeConfiguration:
    """Valida la integridad de la topología de servicios en docker-compose.yml."""

    @pytest.fixture
    def compose_data(self):
        assert COMPOSE_FILE.exists(), "docker-compose.yml debe existir en la raíz"
        content = COMPOSE_FILE.read_text(encoding="utf-8")
        return yaml.safe_load(content)

    def test_network_definition(self, compose_data):
        """Verifica que la red bridge 'usability_net' esté definida."""
        networks = compose_data.get("networks", {})
        assert "usability_net" in networks
        assert networks["usability_net"]["driver"] == "bridge"

  
    def test_all_eight_services_declared(self, compose_data):
        """Verifica que los 7 nodos A2A y el servicio de infraestructura Playwright MCP estén declarados."""
        services = compose_data.get("services", {})
        expected_services = [
            "playwright-mcp",
            "web-explorer",
            "evaluator-dialogue",
            "evaluator-action",
            "evaluator-structure",
            "evaluator-protection",
            "report-creator",
            "orchestrator",
        ]
        for svc_name in expected_services:
            assert svc_name in services, f"El servicio {svc_name} debe estar presente en docker-compose.yml"

    def test_all_services_connected_to_usability_net(self, compose_data):
        """Verifica que cada uno de los 8 servicios esté conectado a la red usability_net."""
        services = compose_data.get("services", {})
        for svc_name, svc_cfg in services.items():
            assert "usability_net" in svc_cfg.get("networks", []), (
                f"El servicio {svc_name} no está conectado a usability_net"
            )

    def test_all_services_have_healthchecks(self, compose_data):
        """Verifica que cada servicio defina un healthcheck funcional."""
        services = compose_data.get("services", {})
        for svc_name, svc_cfg in services.items():
            hc = svc_cfg.get("healthcheck")
            assert hc is not None, f"El servicio {svc_name} no cuenta con healthcheck configurado"
            assert "test" in hc
            assert "interval" in hc
            assert "timeout" in hc
            assert "retries" in hc

    def test_evidence_volume_mounts_and_read_only_flags(self, compose_data):
        """Verifica que los evaluadores monten el volumen como solo lectura (:ro) y los demás como lectura-escritura."""
        services = compose_data.get("services", {})
        evaluators = [
            "evaluator-dialogue",
            "evaluator-action",
            "evaluator-structure",
            "evaluator-protection",
        ]
        rw_services = [
            "playwright-mcp",
            "web-explorer",
            "orchestrator",
            "report-creator",
        ]

        for svc_name in evaluators:
            vols = services[svc_name].get("volumes", [])
            assert any("./evidence:/app/evidence:ro" in str(v) for v in vols), (
                f"El evaluador {svc_name} debe montar ./evidence:/app/evidence:ro en modo solo-lectura"
            )

        for svc_name in rw_services:
            vols = services[svc_name].get("volumes", [])
            assert any("./evidence:/app/evidence" in str(v) for v in vols), (
                f"El servicio {svc_name} debe montar ./evidence:/app/evidence con permisos de escritura"
            )

    def test_orchestrator_dependency_ordering(self, compose_data):
        """Verifica que el Orquestador espere a que los otros 6 nodos de agentes estén saludables."""
        orch = compose_data.get("services", {}).get("orchestrator", {})
        depends_on = orch.get("depends_on", {})

        required_dependencies = [
            "web-explorer",
            "evaluator-dialogue",
            "evaluator-action",
            "evaluator-structure",
            "evaluator-protection",
            "report-creator",
        ]
        for dep in required_dependencies:
            assert dep in depends_on, f"Orchestrator debe depender de {dep}"
            assert depends_on[dep].get("condition") == "service_healthy"

    def test_web_explorer_depends_on_playwright_mcp_healthy(self, compose_data):
        """Verifica que Web Explorer espere a que playwright-mcp esté saludable."""
        explorer = compose_data.get("services", {}).get("web-explorer", {})
        depends_on = explorer.get("depends_on", {})
        assert "playwright-mcp" in depends_on
        assert depends_on["playwright-mcp"].get("condition") == "service_healthy"

    def test_playwright_mcp_security_and_shm(self, compose_data):
        """Verifica la configuración de memoria compartida y permisos para Chromium."""
        mcp = compose_data.get("services", {}).get("playwright-mcp", {})
        assert mcp.get("shm_size") == "1gb"
        assert mcp.get("user") == "root"
