"""Enumeraciones para las 10 heurísticas de Jakob Nielsen y dimensiones de evaluación."""

from enum import Enum


class HeuristicId(str, Enum):
    """Identificadores oficiales de las 10 heurísticas de Jakob Nielsen."""
    H1 = "H1"
    H2 = "H2"
    H3 = "H3"
    H4 = "H4"
    H5 = "H5"
    H6 = "H6"
    H7 = "H7"
    H8 = "H8"
    H9 = "H9"
    H10 = "H10"


class EvaluatorDimension(str, Enum):
    """Las cuatro dimensiones funcionales de evaluación heurística."""
    DIALOGUE = "dialogue"
    ACTION = "action"
    STRUCTURE = "structure"
    PROTECTION = "protection"


HEURISTIC_NAMES: dict[HeuristicId, str] = {
    HeuristicId.H1: "Visibilidad del estado del sistema",
    HeuristicId.H2: "Relación entre el sistema y el mundo real",
    HeuristicId.H3: "Control y libertad del usuario",
    HeuristicId.H4: "Consistencia y estándares",
    HeuristicId.H5: "Prevención de errores",
    HeuristicId.H6: "Reconocimiento antes que recuerdo",
    HeuristicId.H7: "Flexibilidad y eficiencia de uso",
    HeuristicId.H8: "Diseño estético y minimalista",
    HeuristicId.H9: "Ayuda para reconocer, diagnosticar y recuperar errores",
    HeuristicId.H10: "Ayuda y documentación",
}

DIMENSION_HEURISTICS: dict[EvaluatorDimension, list[HeuristicId]] = {
    EvaluatorDimension.DIALOGUE: [HeuristicId.H1, HeuristicId.H2, HeuristicId.H10],
    EvaluatorDimension.ACTION: [HeuristicId.H3, HeuristicId.H7],
    EvaluatorDimension.STRUCTURE: [HeuristicId.H4, HeuristicId.H6, HeuristicId.H8],
    EvaluatorDimension.PROTECTION: [HeuristicId.H5, HeuristicId.H9],
}
