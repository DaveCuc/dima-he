"""Enumeración para la escala de severidad de usabilidad de Jakob Nielsen."""

from enum import IntEnum


class NielsenSeverity(IntEnum):
    """Escala de severidad de Nielsen (0 a 4)."""
    NOT_A_PROBLEM = 0
    COSMETIC = 1
    MINOR = 2
    MAJOR = 3
    CATASTROPHIC = 4


SEVERITY_DESCRIPTIONS: dict[NielsenSeverity, str] = {
    NielsenSeverity.NOT_A_PROBLEM: "No se considera un problema de usabilidad.",
    NielsenSeverity.COSMETIC: "Problema cosmético: solo se arregla si sobra tiempo en el proyecto.",
    NielsenSeverity.MINOR: "Problema menor: baja prioridad de corrección.",
    NielsenSeverity.MAJOR: "Problema mayor: alta prioridad, debe corregirse.",
    NielsenSeverity.CATASTROPHIC: "Catástrofe de usabilidad: imperativo resolverlo antes de desplegar.",
}
