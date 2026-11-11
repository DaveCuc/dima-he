"""Contrato Pydantic v2 para evidencias físicas persistidas en disco."""

from typing import Optional
from pydantic import BaseModel, Field, field_validator
from shared.enums.evidence_type import EvidenceType


class EvidenceItem(BaseModel):
    """Metadatos de una evidencia física generada durante la exploración."""
    evidence_id: str = Field(description="Identificador único de la evidencia, ej. ev-scr-001")
    type: EvidenceType = Field(description="Tipo de evidencia física")
    file_path: str = Field(
        description="Ruta relativa física dentro de /app/evidence/evaluations/{evaluation_id}/"
    )
    page_id: str = Field(description="Identificador de la página evaluada, ej. page-home")
    description: str = Field(description="Descripción contextual de la evidencia capturada")
    timestamp: Optional[str] = Field(default=None, description="Marca temporal ISO-8601 de captura")
    source_agent: str = Field(default="web_explorer", description="Agente que generó la evidencia")

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        v_clean = v.strip()
        if not v_clean:
            raise ValueError("El file_path no puede estar vacío.")
        if v_clean.startswith("data:") or ";base64," in v_clean:
            raise ValueError(
                "Guardrail A2A violado: Prohibido transmitir contenido Base64. "
                "Debe ser una ruta física relativa al volumen de evidencias."
            )
        # Normalizar separadores de ruta hacia formato POSIX para interoperabilidad en contenedores
        normalized = v_clean.replace("\\", "/")
        return normalized
