"""Contratos Pydantic v2 para hallazgos de usabilidad y esquemas de salida de evaluadores."""

from typing import List, Optional
from pydantic import BaseModel, Field, model_validator
from shared.enums.heuristics import HeuristicId, HEURISTIC_NAMES
from shared.enums.agent_role import EvaluatorAgentId


class FindingLocation(BaseModel):
    """Ubicación precisa del elemento afectado dentro de la interfaz."""
    page: str = Field(description="Identificador de la página o ruta donde se localiza el hallazgo")
    element: str = Field(description="Nombre o etiqueta legible del componente (ej. 'Botón de Reservar')")
    selector: Optional[str] = Field(
        default=None,
        description="Selector CSS o XPath normalizado para localizar el elemento en el DOM"
    )
    coordinates: Optional[str] = Field(
        default=None,
        description="Coordenadas aproximadas en pantalla (ej. 'x: 240, y: 560')"
    )


class UsabilityFinding(BaseModel):
    """Hallazgo formal de usabilidad fundamentado en las 10 heurísticas de Nielsen."""
    finding_id: str = Field(description="Identificador único del hallazgo, ej. find-dia-001")
    evaluation_id: str = Field(description="Identificador de la auditoría correspondiente")
    agent_id: EvaluatorAgentId = Field(description="Agente evaluador que emitió el diagnóstico")
    problem: str = Field(description="Descripción concisa y objetiva del problema de usabilidad detectado")
    heuristic_id: HeuristicId = Field(description="Identificador formal de la heurística vulnerada (H1 a H10)")
    heuristic_name: str = Field(default="", description="Nombre canónico de la heurística de Nielsen")
    justification: str = Field(description="Argumentación fundamentada de por qué se vulnera la heurística")
    location: FindingLocation = Field(description="Ubicación física y selector del componente en la página")
    evidence_ids: List[str] = Field(
        default_factory=list,
        description="Lista de IDs de evidencia física que sustentan el hallazgo (capturas o snapshots)"
    )
    severity: int = Field(
        ge=0,
        le=4,
        description="Escala de Nielsen: 0=No problema, 1=Cosmético, 2=Menor, 3=Mayor, 4=Catastrófico"
    )
    severity_justification: str = Field(
        description="Justificación técnica del nivel de severidad asignado según el impacto en el usuario"
    )
    improvement: str = Field(
        description="Recomendación constructiva y accionable para resolver o mitigar el problema"
    )
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Nivel de certeza estadística del evaluador sobre este hallazgo (0.0 a 1.0)"
    )
    limitations: List[str] = Field(
        default_factory=list,
        description="Condicionantes observados (ej. 'Requiere contrastar con datos dinámicos')"
    )

    @model_validator(mode="after")
    def populate_heuristic_name(self) -> "UsabilityFinding":
        if not self.heuristic_name and self.heuristic_id in HEURISTIC_NAMES:
            self.heuristic_name = HEURISTIC_NAMES[self.heuristic_id]
        return self


class EvaluatorFindingList(BaseModel):
    """Esquema de salida obligatorio (output_schema) para los Nodos 2, 3, 4 y 5.
    
    Garantiza que los evaluadores de Google ADK retornen exclusivamente
    JSON estructurado sin texto conversacional libre.
    """
    findings: List[UsabilityFinding] = Field(
        default_factory=list,
        description="Lista estructurada de hallazgos identificados por el evaluador"
    )


class ConsolidatedFinding(UsabilityFinding):
    """Hallazgo resultante de la consolidación determinista del DeduplicatorAgent."""
    source_agents: List[EvaluatorAgentId] = Field(
        default_factory=list,
        description="Agentes que coincidieron en identificar este hallazgo"
    )
    original_finding_ids: List[str] = Field(
        default_factory=list,
        description="Trazabilidad de IDs originales antes de la deduplicación"
    )


class ConsolidatedFindings(BaseModel):
    """Lista consolidada entregada por el DeduplicatorAgent al Nodo 6 (Report Creator)."""
    evaluation_id: str = Field(description="Identificador de la auditoría")
    findings: List[ConsolidatedFinding] = Field(
        default_factory=list,
        description="Colección de hallazgos desduplicados y consolidados"
    )
    total_raw_findings: int = Field(default=0, ge=0, description="Total de hallazgos antes de deduplicar")
    total_consolidated_findings: int = Field(default=0, ge=0, description="Total de hallazgos tras deduplicar")
    duplicates_removed: int = Field(default=0, ge=0, description="Cantidad de duplicados exactos eliminados")
