"""Generador de reportes de usabilidad en formatos JSON, Markdown y CSV (Nodo 6).

Produce la tríada oficial de reportes requerida por el proyecto:
1. results.json: Datos estructurados completos para consumo programático.
2. report.md: Resumen ejecutivo y tablas formateadas para inserción directa en tesis.
3. report.csv: Datos tabulares limpios para análisis estadístico en hojas de cálculo.
"""

import csv
import io
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Union

from shared.enums.heuristics import HEURISTIC_NAMES
from shared.schemas.finding import ConsolidatedFindings
from shared.utils.file_paths import get_reports_dir, to_relative_posix

logger = logging.getLogger(__name__)

SEVERITY_LABELS = {
    0: "No problema",
    1: "Cosmético",
    2: "Menor",
    3: "Mayor",
    4: "Catastrófico",
}


class ReportGenerator:
    """Genera y persiste físicamente en disco la tríada de reportes de usabilidad."""

    def __init__(self, base_evidence_dir: Union[str, Path] = "evidence"):
        self.base_evidence_dir = Path(base_evidence_dir)

    def calculate_statistics(self, consolidated: ConsolidatedFindings) -> Dict[str, Any]:
        """Calcula métricas estadísticas cuantitativas sobre los hallazgos consolidados."""
        findings = consolidated.findings
        total = len(findings)

        # Distribución por severidad (0-4)
        severity_dist = {i: 0 for i in range(5)}
        for f in findings:
            if 0 <= f.severity <= 4:
                severity_dist[f.severity] += 1

        # Distribución por heurística (H1 a H10)
        heuristic_dist = {f"H{i}": 0 for i in range(1, 11)}
        for f in findings:
            hid = f.heuristic_id.value
            heuristic_dist[hid] = heuristic_dist.get(hid, 0) + 1

        # Severidad promedio
        avg_severity = round(sum(f.severity for f in findings) / total, 2) if total > 0 else 0.0

        # Heurísticas más vulneradas
        sorted_heuristics = sorted(heuristic_dist.items(), key=lambda item: item[1], reverse=True)
        top_violated = [
            {"heuristic_id": hid, "name": HEURISTIC_NAMES.get(hid, hid), "count": count}
            for hid, count in sorted_heuristics if count > 0
        ]

        # Veredicto de usabilidad
        catastrophic_count = severity_dist[4]
        major_count = severity_dist[3]
        if catastrophic_count > 0:
            verdict = "CRÍTICO - Se identificaron problemas catastróficos que impiden el flujo del usuario. Corrección mandatoria previa a despliegue."
        elif major_count > 2:
            verdict = "DESFAVORABLE - Múltiples problemas mayores de usabilidad impactan la experiencia de usuario. Corrección prioritaria requerida."
        elif total > 0:
            verdict = "ACEPTABLE CON OBSERVACIONES - Predominan problemas cosméticos y menores. Se recomienda iterar en las mejoras sugeridas."
        else:
            verdict = "EXCELENTE - No se identificaron problemas heurísticos en las rutas inspeccionadas."

        return {
            "total_findings": total,
            "total_raw_findings": consolidated.total_raw_findings,
            "duplicates_removed": consolidated.duplicates_removed,
            "severity_distribution": {
                f"{lvl} - {SEVERITY_LABELS[lvl]}": count for lvl, count in severity_dist.items()
            },
            "raw_severity_counts": severity_dist,
            "average_severity": avg_severity,
            "heuristic_distribution": heuristic_dist,
            "top_violated_heuristics": top_violated,
            "verdict": verdict,
        }

    def generate_json_report(
        self,
        consolidated: ConsolidatedFindings,
        stats: Dict[str, Any],
    ) -> str:
        """Genera el contenido estructurado de results.json."""
        data = {
            "metadata": {
                "evaluation_id": consolidated.evaluation_id,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "generator": "DIMA-HE Node 6: Report Creator",
                "specification": "Jakob Nielsen 10 Usability Heuristics",
            },
            "statistics": stats,
            "findings": [f.model_dump(mode="json") for f in consolidated.findings],
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    def generate_markdown_report(
        self,
        consolidated: ConsolidatedFindings,
        stats: Dict[str, Any],
    ) -> str:
        """Genera el reporte ejecutivo formateado en Markdown para inserción en tesis."""
        eval_id = consolidated.evaluation_id
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        md_lines = [
            f"# Reporte de Evaluación Heurística de Usabilidad",
            f"**Auditoría ID:** `{eval_id}`  ",
            f"**Fecha de Emisión:** {now_str}  ",
            f"**Metodología:** Evaluación Heurística Multiagente Distribuida (10 Heurísticas de Nielsen)  \n",
            f"---",
            f"\n## 1. Resumen Ejecutivo y Veredicto",
            f"> **Veredicto:** {stats['verdict']}\n",
            f"* **Total de problemas únicos identificados:** {stats['total_findings']}",
            f"* **Hallazgos brutos procesados:** {stats['total_raw_findings']} (Duplicados eliminados: {stats['duplicates_removed']})",
            f"* **Severidad promedio (Escala 0-4):** `{stats['average_severity']}`\n",
            f"### Distribución de Severidad",
            f"| Nivel | Clasificación | Cantidad | Porcentaje |",
            f"| :---: | :--- | :---: | :---: |",
        ]

        total = max(stats["total_findings"], 1)
        for lvl in range(5):
            count = stats["raw_severity_counts"].get(lvl, 0)
            pct = round((count / total) * 100, 1) if stats["total_findings"] > 0 else 0.0
            md_lines.append(f"| {lvl} | {SEVERITY_LABELS[lvl]} | {count} | {pct}% |")

        md_lines.extend([
            f"\n### Heurísticas Más Vulneradas",
            f"| Código | Heurística de Nielsen | Hallazgos |",
            f"| :---: | :--- | :---: |",
        ])
        for item in stats["top_violated_heuristics"]:
            md_lines.append(f"| **{item['heuristic_id']}** | {item['name']} | {item['count']} |")

        md_lines.extend([
            f"\n---",
            f"\n## 2. Detalle Exhaustivo de Hallazgos Consolidados\n",
        ])

        for idx, f in enumerate(consolidated.findings, 1):
            sev_label = SEVERITY_LABELS.get(f.severity, f"Nivel {f.severity}")
            agents_str = ", ".join(f.source_agents)
            md_lines.extend([
                f"### {idx}. [{f.heuristic_id}] {f.problem}",
                f"* **ID Hallazgo:** `{f.finding_id}`",
                f"* **Heurística:** {f.heuristic_id} - {f.heuristic_name}",
                f"* **Severidad:** **{f.severity}/4 ({sev_label})**",
                f"* **Ubicación:** Página `{f.location.page}` | Componente `{f.location.element}` (`{f.location.selector or 'N/A'}`)",
                f"* **Agentes Reportantes:** `{agents_str}`",
                f"\n**Justificación Técnica:**  ",
                f"{f.justification}\n",
                f"**Recomendación de Mejora:**  ",
                f"{f.improvement}\n",
                f"---",
            ])

        return "\n".join(md_lines)

    def generate_csv_report(
        self,
        consolidated: ConsolidatedFindings,
    ) -> str:
        """Genera el contenido CSV tabular delimitado por comas para análisis estadístico."""
        output = io.StringIO()
        fieldnames = [
            "finding_id",
            "evaluation_id",
            "heuristic_id",
            "heuristic_name",
            "severity",
            "severity_label",
            "page",
            "element",
            "selector",
            "problem",
            "justification",
            "improvement",
            "confidence",
            "source_agents",
            "original_finding_ids",
        ]

        writer = csv.DictWriter(output, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()

        for f in consolidated.findings:
            writer.writerow({
                "finding_id": f.finding_id,
                "evaluation_id": f.evaluation_id,
                "heuristic_id": f.heuristic_id.value,
                "heuristic_name": f.heuristic_name,
                "severity": f.severity,
                "severity_label": SEVERITY_LABELS.get(f.severity, str(f.severity)),
                "page": f.location.page,
                "element": f.location.element,
                "selector": f.location.selector or "",
                "problem": f.problem,
                "justification": f.justification,
                "improvement": f.improvement,
                "confidence": f.confidence if f.confidence is not None else "",
                "source_agents": "; ".join(f.source_agents),
                "original_finding_ids": "; ".join(f.original_finding_ids),
            })

        return output.getvalue()

    def generate_and_save_all(
        self,
        consolidated: ConsolidatedFindings,
    ) -> Dict[str, Any]:
        """Calcula métricas, genera los 3 reportes y los persiste físicamente en disco."""
        eval_id = consolidated.evaluation_id
        reports_dir = get_reports_dir(self.base_evidence_dir, eval_id)
        reports_dir.mkdir(parents=True, exist_ok=True)

        stats = self.calculate_statistics(consolidated)

        # 1. results.json
        json_content = self.generate_json_report(consolidated, stats)
        json_file = reports_dir / "results.json"
        json_file.write_text(json_content, encoding="utf-8")

        # 2. report.md
        md_content = self.generate_markdown_report(consolidated, stats)
        md_file = reports_dir / "report.md"
        md_file.write_text(md_content, encoding="utf-8")

        # 3. report.csv
        csv_content = self.generate_csv_report(consolidated)
        csv_file = reports_dir / "report.csv"
        csv_file.write_text(csv_content, encoding="utf-8", newline="")

        logger.info(f"Tríada de reportes persistida exitosamente en {reports_dir}")

        return {
            "evaluation_id": eval_id,
            "statistics": stats,
            "files": {
                "json": to_relative_posix(json_file, self.base_evidence_dir),
                "markdown": to_relative_posix(md_file, self.base_evidence_dir),
                "csv": to_relative_posix(csv_file, self.base_evidence_dir),
            },
        }
