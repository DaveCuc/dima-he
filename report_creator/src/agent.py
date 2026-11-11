"""Agente y lógica del Nodo 6 (Report Creator).

Implementa el agente generador de reportes de usabilidad en los formatos
requeridos por el proyecto (results.json, report.md, report.csv).
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

from shared.schemas.finding import ConsolidatedFindings
from report_creator.src.generator import ReportGenerator

logger = logging.getLogger(__name__)


class ReportCreatorAgent:
    """Agente del Nodo 6 responsable de la síntesis y generación física de reportes."""

    def __init__(
        self,
        node_id: str = "node_6_report_creator",
        name: str = "Generador de Reportes y Síntesis",
        port: int = 8006,
        base_evidence_dir: Union[str, Path] = "evidence",
    ):
        self.node_id = node_id
        self.name = name
        self.port = port
        self.base_evidence_dir = Path(base_evidence_dir)
        self.generator = ReportGenerator(base_evidence_dir=self.base_evidence_dir)

    def generate_reports(
        self,
        consolidated: ConsolidatedFindings,
        base_evidence_dir: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        """Genera y persiste físicamente la tríada oficial de reportes."""
        generator = self.generator
        if base_evidence_dir is not None:
            generator = ReportGenerator(base_evidence_dir=base_evidence_dir)

        logger.info(f"Generando tríada de reportes para auditoría [{consolidated.evaluation_id}]...")
        return generator.generate_and_save_all(consolidated)

    def get_agent_card(self) -> Dict[str, Any]:
        """Genera la Agent Card A2A para el Nodo 6 (Report Creator)."""
        return {
            "name": self.node_id,
            "description": f"{self.name}. Consolida métricas y persiste la tríada de reportes (results.json, report.md, report.csv).",
            "version": "1.0.0",
            "url": f"http://localhost:{self.port}/",
            "protocol_binding": "JSONRPC",
            "skills": [
                {
                    "id": "generate_reports",
                    "name": "Generación de Tríada de Reportes de Usabilidad",
                    "description": "Calcula métricas estadísticas y genera reportes en JSON, Markdown y CSV en el volumen de evidencias.",
                    "input_schema": ConsolidatedFindings.model_json_schema(),
                    "output_schema": {
                        "type": "object",
                        "properties": {
                            "evaluation_id": {"type": "string"},
                            "statistics": {"type": "object"},
                            "files": {
                                "type": "object",
                                "properties": {
                                    "json": {"type": "string"},
                                    "markdown": {"type": "string"},
                                    "csv": {"type": "string"},
                                },
                            },
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


def create_report_creator_agent(
    base_evidence_dir: Union[str, Path] = "evidence",
) -> ReportCreatorAgent:
    """Fábrica para instanciar el ReportCreatorAgent."""
    return ReportCreatorAgent(base_evidence_dir=base_evidence_dir)
