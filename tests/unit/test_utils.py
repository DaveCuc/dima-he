"""Pruebas unitarias para utilidades de rutas de archivos."""

import tempfile
from pathlib import Path
from shared.utils.file_paths import (
    ensure_evaluation_directories,
    to_relative_posix,
    get_evaluation_base_dir,
    get_reports_dir,
)


class TestFilePathUtils:
    """Valida la creación y manejo portable de rutas del volumen de evidencias."""

    def test_ensure_evaluation_directories(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            eval_dirs = ensure_evaluation_directories(tmp_dir, "eval-test-01")
            assert eval_dirs["base"].exists()
            assert eval_dirs["screenshots"].exists()
            assert eval_dirs["snapshots"].exists()
            assert eval_dirs["dom"].exists()
            assert eval_dirs["findings"].exists()
            assert eval_dirs["reports"].exists()

    def test_to_relative_posix(self):
        base = Path("C:/app/evidence")
        target = Path("C:/app/evidence/evaluations/eval-001/screenshots/shot1.png")
        rel_posix = to_relative_posix(target, base)
        assert "\\" not in rel_posix
        assert rel_posix == "evaluations/eval-001/screenshots/shot1.png"
