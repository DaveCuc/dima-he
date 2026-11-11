"""Definición del Agente Evaluador de Diálogo y Visibilidad (Nodo 2).

Responsable de evaluar las heurísticas H1, H2 y H10 en la interfaz web.
"""

from shared.enums.agent_role import EvaluatorAgentId
from evaluators.base_evaluator import BaseHeuristicEvaluator


def create_dialogue_evaluator() -> BaseHeuristicEvaluator:
    """Instancia el evaluador especializado en diálogo, visibilidad y ayuda."""
    return BaseHeuristicEvaluator(
        dimension="dialogue",
        node_id=EvaluatorAgentId.DIALOGUE,
        port=8002,
        heuristics=["H1", "H2", "H10"],
        name="Evaluador de Diálogo, Visibilidad y Ayuda",
        focus_description="Comunicación interfaz-usuario, microcopy, indicadores de estado/carga, lenguaje comprensible y documentación de ayuda.",
    )
