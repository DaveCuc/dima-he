"""Definición del Agente Evaluador de Acción y Control (Nodo 3).

Responsable de evaluar las heurísticas H3 y H7 en la interfaz web.
"""

from shared.enums.agent_role import EvaluatorAgentId
from evaluators.base_evaluator import BaseHeuristicEvaluator


def create_action_evaluator() -> BaseHeuristicEvaluator:
    """Instancia el evaluador especializado en acción y control del usuario."""
    return BaseHeuristicEvaluator(
        dimension="action",
        node_id=EvaluatorAgentId.ACTION,
        port=8003,
        heuristics=["H3", "H7"],
        name="Evaluador de Acción y Control del Usuario",
        focus_description="Flujos de interacción, botones de cancelar/regresar, cierre de modales, controles interactivos, atajos y eficiencia operativa.",
    )
