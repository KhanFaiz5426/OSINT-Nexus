"""Report generator - HTML investigation report generation.

Tasks 8.3-8.6: Renders investigation data into HTML (Jinja2).
"""
from __future__ import annotations

import json
import logging
import re
import uuid
import os
from pathlib import Path
from typing import Any
import os

logger = logging.getLogger(__name__)

def _get_base_dir() -> Path:
    import sys
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / "app"
    return Path(__file__).resolve().parent.parent

_REPORTS_DIR = _get_base_dir() / "reports_output"
_TEMPLATES_DIR = _get_base_dir() / "templates"


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
    """Render an HTML investigation or workspace report using Jinja2."""
    from jinja2 import Environment, FileSystemLoader

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=True,
    )
    
    is_workspace = data.get("is_workspace_report", False)
    template_name = "workspace_report.html" if is_workspace else "report.html"
    template = env.get_template(template_name)

    if is_workspace:
        filename = f"workspace_report_{uuid.uuid4().hex[:8]}.html"
        html_content = template.render(**data)
    else:
        inv = data["investigation"]
        filename = f"report_{_safe_filename(inv['name'])}_{uuid.uuid4().hex[:8]}.html"
        html_content = template.render(
            investigation=inv,
            entities=data["entities"],
            observations=data["observations"],
            relationships=data["relationships"],
            activity_log=data["activity_log"],
            ai_analysis=data["ai_analysis"],
            generated_at=data["generated_at"],
            sources_used=data.get("sources_used", []),
            notes=data.get("notes", []),
        )
    
    _ensure_reports_dir()
    filepath = _REPORTS_DIR / filename
    filepath.write_text(html_content, encoding="utf-8")
    return str(filepath)


FORMAT_GENERATORS = {
    "html": generate_html_report,
}


def generate_report(data: dict[str, Any], fmt: str = "html") -> str:
    """Generate an investigation or workspace report in the specified format.

    Args:
        data: Aggregated report data.
        fmt: One of 'html'.

    Returns:
        Absolute path to the generated file.

    Raises:
        ValueError: If format is not supported.
    """
    generator = FORMAT_GENERATORS.get(fmt)
    if generator is None:
        raise ValueError(f"Unsupported report format: {fmt}")
    return generator(data)
