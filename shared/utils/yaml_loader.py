"""Utilidad para la carga y validación de archivos de configuración YAML."""

from pathlib import Path
from typing import Any, Dict
import yaml


def load_yaml(file_path: Path | str) -> Dict[str, Any]:
    """Carga de forma segura un archivo YAML y retorna su contenido estructurado."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Archivo de configuración no encontrado: {path.resolve()}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def get_heuristics_config(config_dir: Path | str = "config") -> Dict[str, Any]:
    """Carga la configuración de heurísticas desde config/heuristics.yaml."""
    return load_yaml(Path(config_dir) / "heuristics.yaml")


def get_agents_config(config_dir: Path | str = "config") -> Dict[str, Any]:
    """Carga la configuración de nodos y red desde config/agents.yaml."""
    return load_yaml(Path(config_dir) / "agents.yaml")


def get_evaluation_config(config_dir: Path | str = "config") -> Dict[str, Any]:
    """Carga los parámetros de evaluación desde config/evaluation.yaml."""
    return load_yaml(Path(config_dir) / "evaluation.yaml")
