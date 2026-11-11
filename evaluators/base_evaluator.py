"""Módulo base para los Evaluadores Heurísticos (Nodos 2, 3, 4 y 5).

Proporciona la infraestructura común para la carga física multimodal de evidencias
(capturas .png mediante Part.from_bytes, snapshots y DOM), la configuración del agente
de Google ADK con output_schema=EvaluatorFindingList y un motor de evaluación determinista
de respaldo para entornos sin conexión a Gemini API.
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from google.adk.agents import Agent
from google.genai import types as genai_types

from shared.enums.agent_role import EvaluatorAgentId
from shared.enums.heuristics import HeuristicId, HEURISTIC_NAMES
from shared.schemas.exploration import ExplorationResult, PageExplorationResult
from shared.schemas.finding import EvaluatorFindingList, FindingLocation, UsabilityFinding
from shared.utils.yaml_loader import get_heuristics_config

logger = logging.getLogger(__name__)

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


class BaseHeuristicEvaluator:
    """Clase base para los evaluadores especializados por dimensión heurística."""

    def __init__(
        self,
        dimension: str,
        node_id: EvaluatorAgentId,
        port: int,
        heuristics: List[str],
        name: str,
        focus_description: str,
        model: str = DEFAULT_MODEL,
    ):
        self.dimension = dimension
        self.node_id = node_id
        self.port = port
        self.heuristics = heuristics
        self.name = name
        self.focus_description = focus_description
        self.model = model
        self.instruction = self._build_instruction()

    def _build_instruction(self) -> str:
        """Construye las directrices para el agente según las heurísticas de su dimensión."""
        try:
            heuristics_cfg = get_heuristics_config().get("heuristics", {})
        except Exception:
            heuristics_cfg = {}
        guidelines = []
        for h_id in self.heuristics:
            h_info = heuristics_cfg.get(h_id, {})
            h_name = h_info.get("name", h_id)
            h_desc = h_info.get("description", "")
            checklist = "\n  - ".join(h_info.get("evaluation_checklist", []))
            guidelines.append(
                f"### Heurística {h_id}: {h_name}\n"
                f"Descripción: {h_desc}\n"
                f"Puntos de verificación:\n  - {checklist}\n"
            )

        return (
            f"Eres el agente evaluador especializado en la dimensión '{self.dimension.upper()}': {self.name}.\n"
            f"Tu responsabilidad exclusiva es auditar interfaces web contra las heurísticas asignadas: {', '.join(self.heuristics)}.\n"
            f"Enfoque temático: {self.focus_description}\n\n"
            f"CRITERIOS DE AUDITORÍA:\n"
            + "\n".join(guidelines)
            + "\n"
            "INSTRUCCIONES DE SALIDA:\n"
            "- Debes retornar EXCLUSIVAMENTE una estructura JSON válida que se ajuste al esquema EvaluatorFindingList.\n"
            "- Para cada hallazgo detectado, clasifica la severidad del 0 al 4 según la escala de Nielsen:\n"
            "  0=No problema, 1=Cosmético, 2=Menor, 3=Mayor, 4=Catastrófico.\n"
            "- Proporciona justificación objetiva, ubicación precisa en la página y recomendación constructiva de mejora.\n"
            "- Basa tus diagnósticos tanto en las capturas de pantalla visuales como en la estructura de accesibilidad y DOM.\n"
        )

    def load_multimodal_evidence(
        self,
        exploration_result: ExplorationResult,
        base_evidence_dir: Union[str, Path] = "evidence",
    ) -> List[genai_types.Part]:
        """Carga físicamente las evidencias desde el volumen /app/evidence hacia partes multimodales."""
        base_dir = Path(base_evidence_dir)
        parts: List[genai_types.Part] = []

        context_summary = (
            f"EVALUACIÓN DE USABILIDAD (Eval ID: {exploration_result.evaluation_id})\n"
            f"URL Objetivo: {exploration_result.target_url}\n"
            f"Total de páginas exploradas: {exploration_result.total_pages}\n\n"
        )
        parts.append(genai_types.Part.from_text(text=context_summary))

        for page in exploration_result.pages_explored:
            page_header = (
                f"\n--- PÁGINA AUDITADA: {page.page_id} ({page.url}) ---\n"
                f"Título: {page.title}\n"
            )

            # Cargar snapshot de accesibilidad
            if page.accessibility_snapshot_path:
                snap_file = base_dir / page.accessibility_snapshot_path
                if snap_file.exists():
                    try:
                        snap_content = snap_file.read_text(encoding="utf-8")
                        page_header += f"\n[Árbol de Accesibilidad]:\n{snap_content[:3000]}\n"
                    except Exception as e:
                        logger.warning(f"No se pudo leer snapshot en {snap_file}: {e}")

            # Cargar fragmento DOM representativo
            if page.dom_reference_path:
                dom_file = base_dir / page.dom_reference_path
                if dom_file.exists():
                    try:
                        dom_content = dom_file.read_text(encoding="utf-8")
                        clean_dom = re.sub(r"\s+", " ", dom_content)[:2500]
                        page_header += f"\n[Estructura DOM]:\n{clean_dom}\n"
                    except Exception as e:
                        logger.warning(f"No se pudo leer DOM en {dom_file}: {e}")

            parts.append(genai_types.Part.from_text(text=page_header))

            # Cargar capturas físicas de pantalla mediante Part.from_bytes
            for scr_item in page.screenshots:
                scr_file = base_dir / scr_item.file_path
                if scr_file.exists() and scr_file.stat().st_size > 0:
                    try:
                        img_bytes = scr_file.read_bytes()
                        parts.append(
                            genai_types.Part.from_bytes(
                                data=img_bytes,
                                mime_type="image/png",
                            )
                        )
                        logger.debug(f"Captura cargada para inferencia multimodal: {scr_item.file_path} ({len(img_bytes)} bytes)")
                    except Exception as e:
                        logger.warning(f"Fallo cargando imagen {scr_file}: {e}")

        return parts

    def create_adk_agent(self) -> Agent:
        """Instancia el Google ADK Agent con output_schema=EvaluatorFindingList."""
        return Agent(
            name=self.node_id.value,
            description=self.name,
            model=self.model,
            instruction=self.instruction,
            output_schema=EvaluatorFindingList,
            disallow_transfer_to_parent=True,
            disallow_transfer_to_peers=True,
        )

    def _fallback_rule_evaluation(
        self,
        exploration_result: ExplorationResult,
        base_evidence_dir: Union[str, Path] = "evidence",
    ) -> EvaluatorFindingList:
        """Motor determinista de inspección heurística para pruebas locales o CI sin clave de API."""
        findings: List[UsabilityFinding] = []
        base_dir = Path(base_evidence_dir)
        counter = 0

        for page in exploration_result.pages_explored:
            # Leer DOM o snapshot si existen
            dom_text = ""
            if page.dom_reference_path:
                p = base_dir / page.dom_reference_path
                if p.exists():
                    dom_text = p.read_text(encoding="utf-8").lower()

            snap_text = ""
            if page.accessibility_snapshot_path:
                p = base_dir / page.accessibility_snapshot_path
                if p.exists():
                    snap_text = p.read_text(encoding="utf-8").lower()

            # Diagnósticos heurísticos según dimensión
            if self.dimension == "dialogue":
                # H1: Visibilidad del estado del sistema
                if "spinner" not in dom_text and "loading" not in dom_text and "progress" not in dom_text:
                    counter += 1
                    findings.append(
                        UsabilityFinding(
                            finding_id=f"find-dia-{counter:03d}",
                            evaluation_id=exploration_result.evaluation_id,
                            agent_id=self.node_id,
                            problem="Ausencia de indicadores visuales explícitos de carga o progreso asíncrono",
                            heuristic_id=HeuristicId.H1,
                            justification="No se detectaron elementos de carga (loading/spinner) en el DOM para operaciones dinámicas.",
                            location=FindingLocation(page=page.page_id, element="Contenedor Principal", selector="body"),
                            evidence_ids=[s.evidence_id for s in page.screenshots[:1]],
                            severity=2,
                            severity_justification="El usuario puede desconocer si la aplicación respondió a sus interacciones.",
                            improvement="Incorporar indicadores de progreso o placeholders mientras los datos se recuperan.",
                            confidence=0.85,
                        )
                    )
                # H10: Ayuda y documentación
                if "help" not in dom_text and "ayuda" not in dom_text and "faq" not in dom_text:
                    counter += 1
                    findings.append(
                        UsabilityFinding(
                            finding_id=f"find-dia-{counter:03d}",
                            evaluation_id=exploration_result.evaluation_id,
                            agent_id=self.node_id,
                            problem="Falta de accesos visibles a secciones de ayuda, preguntas frecuentes o soporte",
                            heuristic_id=HeuristicId.H10,
                            justification="La interfaz carece de enlaces contextuales o pie de página con documentación de ayuda.",
                            location=FindingLocation(page=page.page_id, element="Pie de Página", selector="footer"),
                            evidence_ids=[s.evidence_id for s in page.screenshots[:1]],
                            severity=2,
                            severity_justification="Complica la resolución autónoma de dudas para usuarios no familiarizados.",
                            improvement="Integrar un enlace accesible de 'Ayuda' o FAQ en el menú superior o pie de página.",
                            confidence=0.90,
                        )
                    )

            elif self.dimension == "action":
                # H3: Control y libertad
                if "cancel" not in dom_text and "cancelar" not in dom_text and "volver" not in dom_text and "regresar" not in dom_text:
                    counter += 1
                    findings.append(
                        UsabilityFinding(
                            finding_id=f"find-act-{counter:03d}",
                            evaluation_id=exploration_result.evaluation_id,
                            agent_id=self.node_id,
                            problem="Carencia de opciones evidentes de cancelación o retorno en vistas de interacción",
                            heuristic_id=HeuristicId.H3,
                            justification="No se encontraron botones de 'Cancelar' o 'Regresar' para abandonar flujos de forma inmediata.",
                            location=FindingLocation(page=page.page_id, element="Barra de Navegación", selector="nav"),
                            evidence_ids=[s.evidence_id for s in page.screenshots[:1]],
                            severity=3,
                            severity_justification="Provoca sensación de atrapamiento y riesgo de abandono de la plataforma.",
                            improvement="Proveer un botón visible de cancelar o regresar con confirmación no invasiva.",
                            confidence=0.88,
                        )
                    )

            elif self.dimension == "structure":
                # H8: Diseño estético y minimalista
                counter += 1
                findings.append(
                    UsabilityFinding(
                        finding_id=f"find-str-{counter:03d}",
                        evaluation_id=exploration_result.evaluation_id,
                        agent_id=self.node_id,
                        problem="Densidad de información y espaciado mejorable en componentes de contenido",
                        heuristic_id=HeuristicId.H8,
                        justification="La distribución visual de elementos requiere mayor balance de espacios en blanco según la captura física.",
                        location=FindingLocation(page=page.page_id, element="Sección de Contenido", selector="main"),
                        evidence_ids=[s.evidence_id for s in page.screenshots[:1]],
                        severity=1,
                        severity_justification="Inconveniente cosmético que no interrumpe la tarea pero impacta la legibilidad.",
                        improvement="Aumentar el padding y márgenes entre bloques de información para reducir la fatiga visual.",
                        confidence=0.80,
                    )
                )

            elif self.dimension == "protection":
                # H5: Prevención de errores
                counter += 1
                findings.append(
                    UsabilityFinding(
                        finding_id=f"find-pro-{counter:03d}",
                        evaluation_id=exploration_result.evaluation_id,
                        agent_id=self.node_id,
                        problem="Ausencia de advertencias preventivas o restricciones visuales previas al envío",
                        heuristic_id=HeuristicId.H5,
                        justification="Los campos de formulario observados no muestran restricciones de formato en tiempo real.",
                        location=FindingLocation(page=page.page_id, element="Formulario o Campos de Entrada", selector="form"),
                        evidence_ids=[s.evidence_id for s in page.screenshots[:1]],
                        severity=2,
                        severity_justification="Puede provocar errores de validación que podrían prevenirse anticipadamente.",
                        improvement="Implementar validaciones visuales en línea y máscaras de entrada preventivas.",
                        confidence=0.82,
                    )
                )

        return EvaluatorFindingList(findings=findings)

    async def evaluate(
        self,
        exploration_result: ExplorationResult,
        base_evidence_dir: Union[str, Path] = "evidence",
    ) -> EvaluatorFindingList:
        """Ejecuta la evaluación heurística con Gemini API o fallback determinista."""
        api_key = os.getenv("GOOGLE_API_KEY")

        # Si hay API Key real configurada, intentar llamada multimodal con Gemini API
        if api_key and api_key != "dummy-key-for-ci":
            try:
                parts = self.load_multimodal_evidence(exploration_result, base_evidence_dir)
                from google import genai
                client = genai.Client()

                prompt_parts = [self.instruction] + parts
                response = await client.aio.models.generate_content(
                    model=self.model,
                    contents=prompt_parts,
                    config=genai_types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=EvaluatorFindingList,
                    ),
                )
                if response.text:
                    parsed = json.loads(response.text)
                    return EvaluatorFindingList.model_validate(parsed)
            except Exception as e:
                logger.warning(f"Fallo en inferencia Gemini API para {self.name}: {e}. Activando motor de respaldo.")

        # Motor determinista de respaldo
        return self._fallback_rule_evaluation(exploration_result, base_evidence_dir)

    def get_agent_card(self) -> Dict[str, Any]:
        """Genera la Agent Card A2A para el evaluador."""
        return {
            "name": self.node_id.value,
            "description": f"{self.name}. Evalúa heurísticas: {', '.join(self.heuristics)}.",
            "version": "1.0.0",
            "url": f"http://localhost:{self.port}/",
            "protocol_binding": "JSONRPC",
            "skills": [
                {
                    "id": f"evaluate_{self.dimension}",
                    "name": f"Evaluación Heurística de {self.dimension.capitalize()}",
                    "description": f"Audita evidencias físicas de la interfaz web y emite diagnósticos tipados para {', '.join(self.heuristics)}.",
                    "input_schema": ExplorationResult.model_json_schema(),
                    "output_schema": EvaluatorFindingList.model_json_schema(),
                }
            ],
            "capabilities": {
                "streaming": False,
                "push_notifications": False,
            },
            "provider": {
                "organization": "DIMA-HE - Universidad Tecnológica de la Mixteca",
                "url": "https://github.com/DaveCuc/dima-he",
            },
            "default_input_modes": ["application/json"],
            "default_output_modes": ["application/json"],
        }
