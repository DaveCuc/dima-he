"""Exportación centralizada de enums del sistema."""

from shared.enums.heuristics import (
    HeuristicId,
    EvaluatorDimension,
    HEURISTIC_NAMES,
    DIMENSION_HEURISTICS,
)
from shared.enums.severity import NielsenSeverity, SEVERITY_DESCRIPTIONS
from shared.enums.evidence_type import EvidenceType
from shared.enums.agent_role import EvaluatorAgentId, EvaluationVersion

__all__ = [
    "HeuristicId",
    "EvaluatorDimension",
    "HEURISTIC_NAMES",
    "DIMENSION_HEURISTICS",
    "NielsenSeverity",
    "SEVERITY_DESCRIPTIONS",
    "EvidenceType",
    "EvaluatorAgentId",
    "EvaluationVersion",
]
