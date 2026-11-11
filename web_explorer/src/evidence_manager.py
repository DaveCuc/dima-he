"""Administrador de evidencias físicas para el Nodo 1 (Web Explorer)."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union, Dict, Any
from shared.enums.evidence_type import EvidenceType
from shared.schemas.evidence import EvidenceItem
from shared.schemas.exploration import PageExplorationResult, ExplorationResult
from shared.utils.file_paths import (
    ensure_evaluation_directories,
    to_relative_posix,
)


class EvidenceManager:
    """Gestiona la creación, nombrado y persistencia física de evidencias en /app/evidence."""

    def __init__(self, base_evidence_dir: Union[str, Path] = "evidence", evaluation_id: str = "eval-001"):
        self.base_evidence_dir = Path(base_evidence_dir)
        self.evaluation_id = evaluation_id
        self.dirs = ensure_evaluation_directories(self.base_evidence_dir, self.evaluation_id)
        self._evidence_counter = 0

    def _next_evidence_id(self, prefix: str = "ev") -> str:
        self._evidence_counter += 1
        return f"{prefix}-{self._evidence_counter:03d}"

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def save_screenshot(
        self,
        page_id: str,
        image_bytes: Optional[bytes] = None,
        source_file_path: Optional[Union[str, Path]] = None,
        description: str = "Captura visual de pantalla",
    ) -> EvidenceItem:
        """Guarda o registra una captura de pantalla física y retorna su EvidenceItem."""
        ev_id = self._next_evidence_id(prefix="ev-scr")
        filename = f"{page_id}_{ev_id}.png"
        target_path = self.dirs["screenshots"] / filename

        if image_bytes is not None:
            target_path.write_bytes(image_bytes)
        elif source_file_path is not None:
            src = Path(source_file_path)
            if src.resolve() != target_path.resolve():
                if src.exists():
                    target_path.write_bytes(src.read_bytes())
                else:
                    raise FileNotFoundError(f"Archivo de captura no encontrado en: {src}")
        else:
            raise ValueError("Debe proporcionarse 'image_bytes' o 'source_file_path'")

        rel_path = to_relative_posix(target_path, self.base_evidence_dir)

        return EvidenceItem(
            evidence_id=ev_id,
            type=EvidenceType.SCREENSHOT,
            file_path=rel_path,
            page_id=page_id,
            description=description,
            timestamp=self._now_iso(),
            source_agent="web_explorer",
        )

    def save_accessibility_snapshot(
        self,
        page_id: str,
        snapshot_content: Union[str, Dict[str, Any]],
        description: str = "Árbol de accesibilidad",
    ) -> EvidenceItem:
        """Guarda en disco el árbol de accesibilidad en formato YAML/JSON."""
        ev_id = self._next_evidence_id(prefix="ev-a11y")
        filename = f"{page_id}_{ev_id}.json"
        target_path = self.dirs["snapshots"] / filename

        if isinstance(snapshot_content, (dict, list)):
            target_path.write_text(json.dumps(snapshot_content, indent=2, ensure_ascii=False), encoding="utf-8")
        else:
            target_path.write_text(str(snapshot_content), encoding="utf-8")

        rel_path = to_relative_posix(target_path, self.base_evidence_dir)

        return EvidenceItem(
            evidence_id=ev_id,
            type=EvidenceType.ACCESSIBILITY_SNAPSHOT,
            file_path=rel_path,
            page_id=page_id,
            description=description,
            timestamp=self._now_iso(),
            source_agent="web_explorer",
        )

    def save_dom_dump(
        self,
        page_id: str,
        html_content: str,
        description: str = "Volcado del DOM",
    ) -> EvidenceItem:
        """Guarda en disco el HTML o volcado de componentes del DOM."""
        ev_id = self._next_evidence_id(prefix="ev-dom")
        filename = f"{page_id}_{ev_id}.html"
        target_path = self.dirs["dom"] / filename
        target_path.write_text(html_content, encoding="utf-8")

        rel_path = to_relative_posix(target_path, self.base_evidence_dir)

        return EvidenceItem(
            evidence_id=ev_id,
            type=EvidenceType.DOM,
            file_path=rel_path,
            page_id=page_id,
            description=description,
            timestamp=self._now_iso(),
            source_agent="web_explorer",
        )

    def build_page_result(
        self,
        page_id: str,
        url: str,
        title: str,
        observed_elements: list[str],
        accessibility_item: Optional[EvidenceItem] = None,
        dom_item: Optional[EvidenceItem] = None,
        screenshots: Optional[list[EvidenceItem]] = None,
        actions_performed: Optional[list[str]] = None,
        page_state: Optional[dict] = None,
        errors: Optional[list[str]] = None,
    ) -> PageExplorationResult:
        """Construye el contrato PageExplorationResult con las evidencias generadas."""
        return PageExplorationResult(
            evaluation_id=self.evaluation_id,
            page_id=page_id,
            url=url,
            title=title,
            observed_elements=observed_elements or [],
            accessibility_snapshot_path=accessibility_item.file_path if accessibility_item else None,
            dom_reference_path=dom_item.file_path if dom_item else None,
            screenshots=screenshots or [],
            actions_performed=actions_performed or [],
            page_state=page_state or {},
            errors=errors or [],
        )

    def build_exploration_result(
        self,
        target_url: str,
        pages_explored: list[PageExplorationResult],
        feedback: Optional[str] = None,
    ) -> ExplorationResult:
        """Construye el contrato consolidado ExplorationResult."""
        total_screens = sum(len(p.screenshots) for p in pages_explored)
        total_errs = sum(len(p.errors) for p in pages_explored)

        return ExplorationResult(
            evaluation_id=self.evaluation_id,
            target_url=target_url,
            pages_explored=pages_explored,
            total_pages=len(pages_explored),
            total_screenshots=total_screens,
            total_errors=total_errs,
            feedback=feedback,
        )
