"""Agente determinista de desduplicación y consolidación de hallazgos (Nodo 0).

Implementa el DeduplicatorAgent como BaseAgent de Google ADK en Python puro.
Agrupa hallazgos duplicados provenientes de múltiples evaluadores preservando
la trazabilidad de origen (source_agents y original_finding_ids).
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types as genai_types

from shared.enums.agent_role import EvaluatorAgentId
from shared.schemas.finding import ConsolidatedFinding, ConsolidatedFindings, UsabilityFinding
from shared.utils.file_paths import get_findings_dir

logger = logging.getLogger(__name__)


class DeduplicatorAgent(BaseAgent):
    """Agente determinista que fusiona y elimina duplicados de hallazgos de usabilidad."""

    base_evidence_dir: str = "evidence"

    def __init__(
        self,
        name: str = "deduplicator_agent",
        base_evidence_dir: Union[str, Path] = "evidence",
        **kwargs,
    ):
        super().__init__(
            name=name,
            description="Consolida y desduplica determinísticamente hallazgos de usabilidad entre evaluadores.",
            **kwargs,
        )
        self.base_evidence_dir = str(base_evidence_dir)

    def _normalize_text(self, text: Optional[str]) -> str:
        """Normaliza cadenas para comparación determinista insensible a puntuación o espacios."""
        if not text:
            return ""
        return re.sub(r"[^\w\s]", "", text.lower()).strip()

    def _build_dedup_key(self, finding: UsabilityFinding) -> str:
        """Construye una clave compuesta única para identificar hallazgos que refieren al mismo problema."""
        page_norm = self._normalize_text(finding.location.page)
        elem_norm = self._normalize_text(finding.location.element)
        selector_norm = self._normalize_text(finding.location.selector or "")
        h_id = finding.heuristic_id.value
        # La clave agrupa por página, heurística y elemento o selector
        target_target = selector_norm if selector_norm else elem_norm
        return f"{page_norm}::{h_id}::{target_target}"

    def deduplicate(
        self,
        evaluation_id: str,
        raw_findings: List[UsabilityFinding],
    ) -> ConsolidatedFindings:
        """Agrupa hallazgos duplicados y construye el contrato ConsolidatedFindings."""
        grouped: Dict[str, List[UsabilityFinding]] = {}
        total_raw = len(raw_findings)

        for finding in raw_findings:
            key = self._build_dedup_key(finding)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(finding)

        consolidated_list: List[ConsolidatedFinding] = []
        counter = 0

        for key, duplicates in grouped.items():
            counter += 1
            primary = duplicates[0]

            # Recolectar agentes de origen y IDs originales sin duplicados
            source_agents: List[EvaluatorAgentId] = []
            for d in duplicates:
                if d.agent_id not in source_agents:
                    source_agents.append(d.agent_id)

            original_ids = [d.finding_id for d in duplicates]

            # Seleccionar la máxima severidad entre los duplicados reportados
            max_severity = max(d.severity for d in duplicates)

            # Unir identificadores de evidencia física
            merged_evidence_ids = list(dict.fromkeys(
                ev_id for d in duplicates for ev_id in d.evidence_ids
            ))

            # Seleccionar la justificación y mejora más completa (la más extensa)
            best_justification = max((d.justification for d in duplicates), key=len)
            best_improvement = max((d.improvement for d in duplicates), key=len)
            best_problem = max((d.problem for d in duplicates), key=len)

            # Promediar nivel de confianza si está disponible
            confidences = [d.confidence for d in duplicates if d.confidence is not None]
            avg_confidence = round(sum(confidences) / len(confidences), 2) if confidences else None

            # Construir el hallazgo consolidado
            cf = ConsolidatedFinding(
                finding_id=f"cons-find-{counter:03d}",
                evaluation_id=evaluation_id,
                agent_id=primary.agent_id,
                problem=best_problem,
                heuristic_id=primary.heuristic_id,
                heuristic_name=primary.heuristic_name,
                justification=best_justification,
                location=primary.location,
                evidence_ids=merged_evidence_ids,
                severity=max_severity,
                severity_justification=primary.severity_justification,
                improvement=best_improvement,
                confidence=avg_confidence,
                source_agents=source_agents,
                original_finding_ids=original_ids,
            )
            consolidated_list.append(cf)

        total_consolidated = len(consolidated_list)
        duplicates_removed = total_raw - total_consolidated

        return ConsolidatedFindings(
            evaluation_id=evaluation_id,
            findings=consolidated_list,
            total_raw_findings=total_raw,
            total_consolidated_findings=total_consolidated,
            duplicates_removed=duplicates_removed,
        )

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """Ejecuta la desduplicación determinista y actualiza el estado de la sesión."""
        state = ctx.session.state if ctx.session else {}
        eval_id = state.get("evaluation_id", "unknown_eval")

        # Recopilar todos los hallazgos brutos desde las distintas dimensiones
        raw_findings_data: List[Dict[str, Any]] = []
        for dim_key in ["findings_dialogue", "findings_action", "findings_structure", "findings_protection"]:
            dim_list = state.get(dim_key, [])
            if isinstance(dim_list, list):
                raw_findings_data.extend(dim_list)

        if not raw_findings_data and "all_raw_findings" in state:
            raw_findings_data = state["all_raw_findings"]

        logger.info(f"DeduplicatorAgent: Procesando {len(raw_findings_data)} hallazgos brutos para [{eval_id}]")

        raw_models: List[UsabilityFinding] = []
        for item in raw_findings_data:
            try:
                raw_models.append(UsabilityFinding.model_validate(item))
            except Exception as e:
                logger.warning(f"DeduplicatorAgent: No se pudo validar hallazgo bruto: {e}")

        # Ejecutar consolidación determinista
        consolidated = self.deduplicate(eval_id, raw_models)

        # Opcional: Persistir en disco en /app/evidence/evaluations/{evaluation_id}/findings/
        try:
            findings_dir = get_findings_dir(self.base_evidence_dir, eval_id)
            findings_dir.mkdir(parents=True, exist_ok=True)
            output_file = findings_dir / "consolidated_findings.json"
            output_file.write_text(
                json.dumps(consolidated.model_dump(mode="json"), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.info(f"Hallazgos consolidados persistidos en: {output_file}")
        except Exception as e:
            logger.warning(f"No se pudo guardar consolidated_findings.json en disco: {e}")

        summary_msg = (
            f"Desduplicación determinista finalizada: {consolidated.total_raw_findings} hallazgos brutos "
            f"consolidados en {consolidated.total_consolidated_findings} únicos "
            f"({consolidated.duplicates_removed} duplicados eliminados)."
        )
        logger.info(summary_msg)

        yield Event(
            author=self.name,
            content=genai_types.Content(parts=[genai_types.Part.from_text(text=summary_msg)]),
            actions=EventActions(
                escalate=False,
                state_delta={
                    "consolidated_findings": consolidated.model_dump(mode="json"),
                    "total_consolidated_findings": consolidated.total_consolidated_findings,
                    "duplicates_removed": consolidated.duplicates_removed,
                },
            ),
        )
