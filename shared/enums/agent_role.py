"""Enumeración de identificadores de agentes en la red A2A."""

from enum import Enum


class EvaluatorAgentId(str, Enum):
    """Identificadores oficiales de los cuatro agentes evaluadores."""
    DIALOGUE = "evaluator_dialogue"
    ACTION = "evaluator_action"
    STRUCTURE = "evaluator_structure"
    PROTECTION = "evaluator_protection"


class EvaluationVersion(str, Enum):
    """Versión de la plataforma evaluada para auditorías comparativas."""
    PRE_REDESIGN = "pre_redesign"
    POST_REDESIGN = "post_redesign"
