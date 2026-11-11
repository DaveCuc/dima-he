"""Definición del Agente Evaluador de Estructura y Consistencia (Nodo 4).

Responsable de evaluar las heurísticas H4, H6 y H8 en la interfaz web.
"""

from shared.enums.agent_role import EvaluatorAgentId
from evaluators.base_evaluator import BaseHeuristicEvaluator


def create_structure_evaluator() -> BaseHeuristicEvaluator:
    """Instancia el evaluador especializado en estructura, consistencia y reconocimiento."""
    return BaseHeuristicEvaluator(
        dimension="structure",
        node_id=EvaluatorAgentId.STRUCTURE,
        port=8004,
        heuristics=["H4", "H6", "H8"],
        name="Evaluador de Estructura, Consistencia y Reconocimiento",
        focus_description="Jerarquía visual, saturación de información, visibilidad de menús/opciones, contraste estructural y consistencia de componentes.",
    )
