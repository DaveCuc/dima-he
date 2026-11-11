"""Pruebas unitarias para EvidenceManager (Nodo 1)."""

import tempfile
from pathlib import Path
from shared.enums.evidence_type import EvidenceType
from web_explorer.src.evidence_manager import EvidenceManager


class TestEvidenceManager:
    """Valida la persistencia física y trazabilidad de evidencias."""

    def test_save_screenshot_from_bytes(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            em = EvidenceManager(base_evidence_dir=tmp_dir, evaluation_id="eval-001")
            dummy_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRdummy_data"
            item = em.save_screenshot(
                page_id="page_home",
                image_bytes=dummy_bytes,
                description="Captura de prueba",
            )
            assert item.type == EvidenceType.SCREENSHOT
            assert "page_home_ev-scr-001.png" in item.file_path
            assert "\\" not in item.file_path

            # Verificar que el archivo existe físicamente
            saved_file = Path(tmp_dir) / item.file_path
            assert saved_file.exists()
            assert saved_file.read_bytes() == dummy_bytes

    def test_save_accessibility_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            em = EvidenceManager(base_evidence_dir=tmp_dir, evaluation_id="eval-001")
            snapshot_data = {"role": "WebArea", "name": "Test Page", "children": []}
            item = em.save_accessibility_snapshot(
                page_id="page_home",
                snapshot_content=snapshot_data,
            )
            assert item.type == EvidenceType.ACCESSIBILITY_SNAPSHOT
            assert "page_home_ev-a11y-001.json" in item.file_path

            saved_file = Path(tmp_dir) / item.file_path
            assert saved_file.exists()
            assert "Test Page" in saved_file.read_text(encoding="utf-8")

    def test_save_dom_dump(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            em = EvidenceManager(base_evidence_dir=tmp_dir, evaluation_id="eval-001")
            html = "<html><body><h1>Reserva Biosfera</h1></body></html>"
            item = em.save_dom_dump(page_id="page_home", html_content=html)
            assert item.type == EvidenceType.DOM
            assert "page_home_ev-dom-001.html" in item.file_path

            saved_file = Path(tmp_dir) / item.file_path
            assert saved_file.exists()
            assert "Reserva Biosfera" in saved_file.read_text(encoding="utf-8")

    def test_build_page_and_exploration_result(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            em = EvidenceManager(base_evidence_dir=tmp_dir, evaluation_id="eval-001")
            scr = em.save_screenshot(page_id="page_home", image_bytes=b"dummy")
            a11y = em.save_accessibility_snapshot(page_id="page_home", snapshot_content="tree")
            dom = em.save_dom_dump(page_id="page_home", html_content="<html></html>")

            page_res = em.build_page_result(
                page_id="page_home",
                url="http://localhost:8000/",
                title="Inicio",
                observed_elements=["header", "nav", "footer"],
                accessibility_item=a11y,
                dom_item=dom,
                screenshots=[scr],
                actions_performed=["Navegar a http://localhost:8000/"],
            )
            assert page_res.accessibility_snapshot_path == a11y.file_path
            assert page_res.dom_reference_path == dom.file_path
            assert len(page_res.screenshots) == 1

            exp_res = em.build_exploration_result(
                target_url="http://localhost:8000",
                pages_explored=[page_res],
            )
            assert exp_res.total_pages == 1
            assert exp_res.total_screenshots == 1
            assert exp_res.total_errors == 0
