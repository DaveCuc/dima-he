"""Contratos Pydantic v2 para los resultados del ciclo de exploración web."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from shared.schemas.evidence import EvidenceItem


class PageExplorationResult(BaseModel):
    """Evidencias y estado recopilado durante la exploración de una página específica."""
    evaluation_id: str = Field(description="Identificador de la auditoría en curso")
    page_id: str = Field(description="Identificador único de la vista o página, ej. page-catalog")
    url: str = Field(description="URL exacta navegada")
    title: str = Field(default="", description="Título de la página según el navegador")
    observed_elements: List[str] = Field(
        default_factory=list,
        description="Resumen de elementos interactivos clave detectados en la interfaz"
    )
    accessibility_snapshot_path: Optional[str] = Field(
        default=None,
        description="Ruta relativa al archivo de snapshot del árbol de accesibilidad en /app/evidence"
    )
    dom_reference_path: Optional[str] = Field(
        default=None,
        description="Ruta relativa al archivo con volcado DOM o selector de componentes en /app/evidence"
    )
    screenshots: List[EvidenceItem] = Field(
        default_factory=list,
        description="Lista de capturas visuales realizadas sobre la página"
    )
    actions_performed: List[str] = Field(
        default_factory=list,
        description="Registro secuencial de acciones seguras ejecutadas (navegación, clics, esperas)"
    )
    page_state: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metadatos adicionales del estado de la página (código HTTP, modales abiertos)"
    )
    errors: List[str] = Field(
        default_factory=list,
        description="Errores o advertencias no fatales registrados durante la carga o interacción"
    )


class ExplorationResult(BaseModel):
    """Contrato consolidado emitido por el Nodo 1 (Web Explorer) hacia el Orquestador."""
    evaluation_id: str = Field(description="Identificador de la evaluación")
    target_url: str = Field(description="URL objetivo base auditada")
    pages_explored: List[PageExplorationResult] = Field(
        default_factory=list,
        description="Colección de resultados por cada página inspeccionada"
    )
    total_pages: int = Field(default=0, ge=0, description="Total de páginas exploradas")
    total_screenshots: int = Field(default=0, ge=0, description="Total de capturas tomadas")
    total_errors: int = Field(default=0, ge=0, description="Total de errores de navegación registrados")
    feedback: Optional[str] = Field(
        default=None,
        description="Retroalimentación emitida por EvidenceValidatorAgent en caso de reintento"
    )
