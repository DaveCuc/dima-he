"""Utilidades para la gestión segura y portable de rutas del volumen de evidencias."""

from pathlib import Path
from typing import Union


def get_evaluation_base_dir(base_path: Union[str, Path], evaluation_id: str) -> Path:
    """Retorna la ruta base para una evaluación específica."""
    return Path(base_path) / "evaluations" / evaluation_id


def get_exploration_dir(base_path: Union[str, Path], evaluation_id: str) -> Path:
    """Retorna el subdirectorio de exploración."""
    return get_evaluation_base_dir(base_path, evaluation_id) / "exploration"


def get_screenshots_dir(base_path: Union[str, Path], evaluation_id: str) -> Path:
    """Retorna el subdirectorio para capturas de pantalla."""
    return get_exploration_dir(base_path, evaluation_id) / "screenshots"


def get_snapshots_dir(base_path: Union[str, Path], evaluation_id: str) -> Path:
    """Retorna el subdirectorio para snapshots de accesibilidad."""
    return get_exploration_dir(base_path, evaluation_id) / "snapshots"


def get_dom_dir(base_path: Union[str, Path], evaluation_id: str) -> Path:
    """Retorna el subdirectorio para volcados DOM."""
    return get_exploration_dir(base_path, evaluation_id) / "dom"


def get_findings_dir(base_path: Union[str, Path], evaluation_id: str) -> Path:
    """Retorna el subdirectorio para archivos de hallazgos por dimensión."""
    return get_evaluation_base_dir(base_path, evaluation_id) / "findings"


def get_reports_dir(base_path: Union[str, Path], evaluation_id: str) -> Path:
    """Retorna el subdirectorio para los reportes finales (json, md, csv)."""
    return get_evaluation_base_dir(base_path, evaluation_id) / "reports"


def ensure_evaluation_directories(base_path: Union[str, Path], evaluation_id: str) -> dict[str, Path]:
    """Crea la estructura física completa de directorios para una evaluación si no existe."""
    dirs = {
        "base": get_evaluation_base_dir(base_path, evaluation_id),
        "screenshots": get_screenshots_dir(base_path, evaluation_id),
        "snapshots": get_snapshots_dir(base_path, evaluation_id),
        "dom": get_dom_dir(base_path, evaluation_id),
        "findings": get_findings_dir(base_path, evaluation_id),
        "reports": get_reports_dir(base_path, evaluation_id),
    }
    for directory in dirs.values():
        directory.mkdir(parents=True, exist_ok=True)
    return dirs


def to_relative_posix(full_path: Union[str, Path], base_dir: Union[str, Path]) -> str:
    """Convierte una ruta absoluta a una ruta relativa en formato POSIX para interoperabilidad A2A."""
    rel = Path(full_path).relative_to(Path(base_dir))
    return rel.as_posix()
