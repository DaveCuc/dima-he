"""Pruebas unitarias para ReportGenerator (Nodo 6)."""

import csv
import io
import json
import pytest
from pathlib import Path
from report_creator.src.generator import ReportGenerator, SEVERITY_LABELS
from shared.enums.agent_role import EvaluatorAgentId
from shared.enums.heuristics import HeuristicId
from shared.schemas.finding import ConsolidatedFinding, ConsolidatedFindings, FindingLocation


@pytest.fixture
def sample_consolidated():
    """Genera un objeto ConsolidatedFindings de prueba con múltiples hallazgos."""
    cf1 = ConsolidatedFinding(
        finding_id="cons-find-001",
        evaluation_id="eval-rep-001",
        agent_id=EvaluatorAgentId.DIALOGUE,
        problem="Ausencia de indicadores de estado en operaciones asíncronas",
        heuristic_id=HeuristicId.H1,
        heuristic_name="Visibilidad del estado del sistema",
        justification="No se despliega indicador durante la solicitud de datos.",
        location=FindingLocation(page="dashboard", element="DataTable", selector="#table-wrapper"),
        evidence_ids=["ev-scr-001"],
        severity=3,
        severity_justification="Genera confusión mayor en el usuario.",
        improvement="Implementar spinners de carga.",
        confidence=0.92,
        source_agents=[EvaluatorAgentId.DIALOGUE, EvaluatorAgentId.ACTION],
        original_finding_ids=["find-dia-001", "find-act-001"],
    )
    cf2 = ConsolidatedFinding(
        finding_id="cons-find-002",
        evaluation_id="eval-rep-001",
        agent_id=EvaluatorAgentId.STRUCTURE,
        problem="Desalineación de botones primarios y secundarios",
        heuristic_id=HeuristicId.H4,
        heuristic_name="Consistencia y estándares",
        justification="Los botones tienen jerarquías cromáticas invertidas.",
        location=FindingLocation(page="login", element="SubmitBtn", selector="button.submit"),
        evidence_ids=["ev-scr-002"],
        severity=1,
        severity_justification="Problema meramente cosmético.",
        improvement="Alinear a la guía de estilos de Tehuacán-Cuicatlán.",
        confidence=0.88,
        source_agents=[EvaluatorAgentId.STRUCTURE],
        original_finding_ids=["find-str-001"],
    )
    return ConsolidatedFindings(
        evaluation_id="eval-rep-001",
        findings=[cf1, cf2],
        total_raw_findings=3,
        total_consolidated_findings=2,
        duplicates_removed=1,
    )


class TestReportGenerator:
    """Valida la generación de reportes en los formatos JSON, MD y CSV."""

    def test_calculate_statistics_metrics(self, sample_consolidated):
        generator = ReportGenerator()
        stats = generator.calculate_statistics(sample_consolidated)

        assert stats["total_findings"] == 2
        assert stats["total_raw_findings"] == 3
        assert stats["duplicates_removed"] == 1
        assert stats["average_severity"] == 2.0  # (3 + 1) / 2
        assert stats["raw_severity_counts"][3] == 1
        assert stats["raw_severity_counts"][1] == 1
        assert stats["raw_severity_counts"][0] == 0
        assert "verdict" in stats
        assert len(stats["top_violated_heuristics"]) == 2

    def test_generate_json_report_structure(self, sample_consolidated):
        generator = ReportGenerator()
        stats = generator.calculate_statistics(sample_consolidated)
        json_str = generator.generate_json_report(sample_consolidated, stats)

        data = json.loads(json_str)
        assert data["metadata"]["evaluation_id"] == "eval-rep-001"
        assert data["metadata"]["generator"] == "DIMA-HE Node 6: Report Creator"
        assert len(data["findings"]) == 2
        assert data["statistics"]["total_findings"] == 2

    def test_generate_markdown_report_tables_and_verdict(self, sample_consolidated):
        generator = ReportGenerator()
        stats = generator.calculate_statistics(sample_consolidated)
        md_str = generator.generate_markdown_report(sample_consolidated, stats)

        assert "# Reporte de Evaluación Heurística de Usabilidad" in md_str
        assert "eval-rep-001" in md_str
        assert "Distribución de Severidad" in md_str
        assert "| Nivel | Clasificación | Cantidad | Porcentaje |" in md_str
        assert "Heurísticas Más Vulneradas" in md_str
        assert "Ausencia de indicadores de estado en operaciones asíncronas" in md_str
        assert "Recomendación de Mejora:" in md_str

    def test_generate_csv_report_columns_and_escaping(self, sample_consolidated):
        generator = ReportGenerator()
        csv_str = generator.generate_csv_report(sample_consolidated)

        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)

        assert len(rows) == 2
        assert rows[0]["finding_id"] == "cons-find-001"
        assert rows[0]["heuristic_id"] == "H1"
        assert rows[0]["severity"] == "3"
        assert rows[0]["source_agents"] == f"{EvaluatorAgentId.DIALOGUE.value}; {EvaluatorAgentId.ACTION.value}"
        assert rows[0]["original_finding_ids"] == "find-dia-001; find-act-001"

        assert rows[1]["finding_id"] == "cons-find-002"
        assert rows[1]["heuristic_id"] == "H4"
        assert rows[1]["severity"] == "1"

    def test_generate_and_save_all_persists_physical_files(self, tmp_path, sample_consolidated):
        temp_evidence = tmp_path / "evidence"
        generator = ReportGenerator(base_evidence_dir=temp_evidence)

        result = generator.generate_and_save_all(sample_consolidated)

        assert result["evaluation_id"] == "eval-rep-001"
        files = result["files"]
        assert "json" in files
        assert "markdown" in files
        assert "csv" in files

        # Verificar existencia física de los 3 archivos en disco
        reports_dir = temp_evidence / "evaluations" / "eval-rep-001" / "reports"
        json_file = reports_dir / "results.json"
        md_file = reports_dir / "report.md"
        csv_file = reports_dir / "report.csv"

        assert json_file.exists()
        assert md_file.exists()
        assert csv_file.exists()

        assert json_file.stat().st_size > 0
        assert md_file.stat().st_size > 0
        assert csv_file.stat().st_size > 0
