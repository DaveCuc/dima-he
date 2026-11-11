"""Exportación centralizada de todos los contratos Pydantic v2 del sistema."""

from shared.schemas.evaluation import (
    ViewportConfig,
    AuthCredentials,
    EvaluationScope,
    EvaluationRequest,
)
from shared.schemas.evidence import EvidenceItem
from shared.schemas.exploration import (
    PageExplorationResult,
    ExplorationResult,
)
from shared.schemas.finding import (
    FindingLocation,
    UsabilityFinding,
    EvaluatorFindingList,
    ConsolidatedFinding,
    ConsolidatedFindings,
)

__all__ = [
    "ViewportConfig",
    "AuthCredentials",
    "EvaluationScope",
    "EvaluationRequest",
    "EvidenceItem",
    "PageExplorationResult",
    "ExplorationResult",
    "FindingLocation",
    "UsabilityFinding",
    "EvaluatorFindingList",
    "ConsolidatedFinding",
    "ConsolidatedFindings",
]
