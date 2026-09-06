"""Report generator — HTML, PDF, JSON, CSV investigation report generation.

Tasks 8.3–8.6: Renders investigation data into HTML (Jinja2), PDF (WeasyPrint),
JSON, and CSV formats. All output is derived from actual stored investigation
data with full source attribution.
"""

from __future__ import annotations

import csv
import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports_output"
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def _ensure_reports_dir() -> Path:
    """Create the reports output directory if it does not exist."""
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return _REPORTS_DIR


def _safe_filename(name: str) -> str:
    """Sanitize a string for use as a filename component.

    SECURITY: Strip path separators, null bytes, and other dangerous chars.
    """
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = re.sub(r"_+", "_", name).strip("_. ")
    return name[:80] if name else "report"


# ── HTML Report ──────────────────────────────────────────────────────────────


def generate_html_report(data: dict[str, Any]) -> str:
    """Render an HTML investigation report using Jinja2.

    Args:
        data: Aggregated report data from collect_report_data().

    Returns:
        Absolute path to the generated HTML file.
    """
    from jinja2 import Environment, FileSystemLoader

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=True,
    )
    template = env.get_template("report.html")

    inv = data["investigation"]
    filename = f"report_{_safe_filename(inv['name'])}_{uuid.uuid4().hex[:8]}.html"
    output_path = _ensure_reports_dir() / filename

    html_content = template.render(
        investigation=inv,
        entities=data["entities"],
        observations=data["observations"],
        relationships=data["relationships"],
        activity_log=data["activity_log"],
        ai_analysis=data["ai_analysis"],
        generated_at=data["generated_at"],
    )

    output_path.write_text(html_content, encoding="utf-8")
    return str(output_path.resolve())


# ── PDF Report ───────────────────────────────────────────────────────────────


def generate_pdf_report(data: dict[str, Any]) -> str:
    """Render an HTML report and convert it to PDF via WeasyPrint.

    Args:
        data: Aggregated report data from collect_report_data().

    Returns:
        Absolute path to the generated PDF file.
    """
    from jinja2 import Environment, FileSystemLoader

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=True,
    )
    template = env.get_template("report.html")

    inv = data["investigation"]
    filename = f"report_{_safe_filename(inv['name'])}_{uuid.uuid4().hex[:8]}.pdf"
    output_path = _ensure_reports_dir() / filename

    html_content = template.render(
        investigation=inv,
        entities=data["entities"],
        observations=data["observations"],
        relationships=data["relationships"],
        activity_log=data["activity_log"],
        ai_analysis=data["ai_analysis"],
        generated_at=data["generated_at"],
    )

    try:
        from weasyprint import HTML

        HTML(string=html_content).write_pdf(str(output_path))
    except ImportError:
        logger.warning("WeasyPrint not installed; falling back to HTML report")
        html_filename = filename.replace(".pdf", ".html")
        html_path = _ensure_reports_dir() / html_filename
        html_path.write_text(html_content, encoding="utf-8")
        return str(html_path.resolve())
    except Exception as exc:
        logger.error("PDF generation failed: %s", exc)
        html_filename = filename.replace(".pdf", ".html")
        html_path = _ensure_reports_dir() / html_filename
        html_path.write_text(html_content, encoding="utf-8")
        return str(html_path.resolve())

    return str(output_path.resolve())


# ── JSON Report ──────────────────────────────────────────────────────────────


def generate_json_report(data: dict[str, Any]) -> str:
    """Export investigation data as a structured JSON file.

    Args:
        data: Aggregated report data from collect_report_data().

    Returns:
        Absolute path to the generated JSON file.
    """
    inv = data["investigation"]
    filename = f"report_{_safe_filename(inv['name'])}_{uuid.uuid4().hex[:8]}.json"
    output_path = _ensure_reports_dir() / filename

    report = {
        "report_type": "osint_nexus_investigation",
        "report_version": "1.0",
        "generated_at": data["generated_at"],
        "investigation": data["investigation"],
        "entities": data["entities"],
        "relationships": data["relationships"],
        "observations": data["observations"],
        "activity_log": data["activity_log"],
        "ai_analysis": data["ai_analysis"],
        "summary": {
            "entity_count": len(data["entities"]),
            "relationship_count": len(data["relationships"]),
            "observation_count": len(data["observations"]),
            "activity_count": len(data["activity_log"]),
        },
    }

    output_path.write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    return str(output_path.resolve())


# ── CSV Export ───────────────────────────────────────────────────────────────


def generate_csv_report(data: dict[str, Any]) -> str:
    """Export entities and observations as CSV files in a zip-like pair.

    Creates two CSV files: one for entities and one for observations.
    Returns the path to the entities CSV (primary export).

    Args:
        data: Aggregated report data from collect_report_data().

    Returns:
        Absolute path to the generated entities CSV file.
    """
    inv = data["investigation"]
    base = f"export_{_safe_filename(inv['name'])}_{uuid.uuid4().hex[:8]}"
    reports_dir = _ensure_reports_dir()

    # ── Entities CSV ─────────────────────────────────────────────────────
    entities_path = reports_dir / f"{base}_entities.csv"
    entity_fields = [
        "id", "type", "value", "confidence", "first_seen",
        "last_seen", "source_count",
    ]
    with open(entities_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=entity_fields, extrasaction="ignore")
        writer.writeheader()
        for ent in data["entities"]:
            writer.writerow({k: ent.get(k, "") for k in entity_fields})

    # ── Observations CSV ─────────────────────────────────────────────────
    obs_path = reports_dir / f"{base}_observations.csv"
    obs_fields = [
        "id", "source_adapter", "collected_at", "method", "target",
        "normalized_value", "confidence", "status",
    ]
    with open(obs_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=obs_fields, extrasaction="ignore")
        writer.writeheader()
        for obs in data["observations"]:
            writer.writerow({k: obs.get(k, "") for k in obs_fields})

    return str(entities_path.resolve())


# ── Format dispatch ──────────────────────────────────────────────────────────


FORMAT_GENERATORS = {
    "html": generate_html_report,
    "pdf": generate_pdf_report,
    "json": generate_json_report,
    "csv": generate_csv_report,
}


def generate_report(data: dict[str, Any], fmt: str) -> str:
    """Generate a report in the specified format.

    Args:
        data: Aggregated report data.
        fmt: One of 'html', 'pdf', 'json', 'csv'.

    Returns:
        Absolute path to the generated file.

    Raises:
        ValueError: If format is not supported.
    """
    generator = FORMAT_GENERATORS.get(fmt)
    if generator is None:
        raise ValueError(f"Unsupported report format: {fmt}")
    return generator(data)
