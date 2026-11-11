"""Definición del Agente Evaluador de Protección y Errores (Nodo 5).

Responsable de evaluar las heurísticas H5 y H9 en la interfaz web.
"""

from shared.enums.agent_role import EvaluatorAgentId
from evaluators.base_evaluator import BaseHeuristicEvaluator


def create_protection_evaluator() -> BaseHeuristicEvaluator:
    """Instancia el evaluador especializado en prevención y recuperación de errores."""
    return BaseHeuristicEvaluator(
        dimension="protection",
        node_id=EvaluatorAgentId.PROTECTION,
        port=8005,
        heuristics=["H5", "H9"],
        name="Evaluador de Protección y Recuperación de Errores",
        focus_description="Validaciones de formularios, restricciones de entrada, confirmaciones ante acciones críticas, claridad de mensajes de error y recuperación sin pérdida de datos.",
    )
