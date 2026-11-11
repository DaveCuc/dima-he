"""Contratos Pydantic v2 para la solicitud de evaluación de interfaces."""

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from shared.enums.agent_role import EvaluationVersion


class ViewportConfig(BaseModel):
    """Configuración de dimensiones del viewport para Chromium."""
    width: int = Field(default=1366, ge=320, le=3840, description="Ancho de ventana en píxeles")
    height: int = Field(default=768, ge=240, le=2160, description="Alto de ventana en píxeles")


class AuthCredentials(BaseModel):
    """Credenciales de prueba opcionales para flujos privados."""
    username: str = Field(description="Usuario de prueba")
    password: str = Field(description="Contraseña de prueba")
    login_url: Optional[str] = Field(default=None, description="URL específica del formulario de login")


class EvaluationScope(BaseModel):
    """Alcance delimitado de la auditoría heurística."""
    pages: List[str] = Field(default_factory=list, description="Lista base de URLs obligatorias")
    modules: List[str] = Field(default_factory=list, description="Módulos funcionales a evaluar")
    flows: List[str] = Field(default_factory=list, description="Flujos de usuario a recorrer")
    max_depth: int = Field(default=1, ge=0, le=2, description="Profundidad máxima de rastreo autónomo")
    auth: Optional[AuthCredentials] = Field(default=None, description="Credenciales para flujos privados si aplica")


class EvaluationRequest(BaseModel):
    """Solicitud formal de evaluación enviada al Nodo 0 (Orquestador)."""
    evaluation_id: str = Field(description="Identificador único de la auditoría, ej. eval-001")
    target_url: str = Field(description="URL objetivo base, ej. http://host.docker.internal:8000")
    version: EvaluationVersion = Field(default=EvaluationVersion.PRE_REDESIGN, description="Versión auditada")
    scope: EvaluationScope = Field(default_factory=EvaluationScope, description="Alcance de páginas y módulos")
    viewport: ViewportConfig = Field(default_factory=ViewportConfig, description="Dimensiones de pantalla")
    instructions: str = Field(
        default="Explorar y evaluar la interfaz siguiendo las rutas indicadas con base en las 10 heurísticas de Nielsen.",
        description="Instrucciones operativas para el ciclo de agentes"
    )

    @field_validator("evaluation_id")
    @classmethod
    def validate_evaluation_id(cls, v: str) -> str:
        v_clean = v.strip()
        if not v_clean:
            raise ValueError("El evaluation_id no puede estar vacío.")
        if any(c in v_clean for c in [" ", "/", "\\", ":", "*", "?", '"', "<", ">", "|"]):
            raise ValueError("El evaluation_id no debe contener espacios ni caracteres inválidos para nombres de carpeta.")
        return v_clean

    @field_validator("target_url")
    @classmethod
    def validate_target_url(cls, v: str) -> str:
        v_clean = v.strip()
        if not (v_clean.startswith("http://") or v_clean.startswith("https://")):
            raise ValueError("La target_url debe comenzar con http:// o https://")
        return v_clean
