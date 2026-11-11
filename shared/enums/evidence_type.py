"""Enumeración para los tipos de evidencia física recopilados en la exploración."""

from enum import Enum


class EvidenceType(str, Enum):
    """Tipos de evidencia física permitidos en el volumen compartido."""
    SCREENSHOT = "screenshot"
    ACCESSIBILITY_SNAPSHOT = "accessibility_snapshot"
    DOM = "dom"
    INTERACTION_LOG = "interaction_log"
    TEXT = "text"
    OTHER = "other"
