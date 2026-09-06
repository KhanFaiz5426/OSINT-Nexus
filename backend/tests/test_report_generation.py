"""Tests for report generation (Phase 8).

Tests cover report data collection, HTML/JSON/CSV report generation,
and API endpoint integration. These tests use sample investigation
data — never fabricated or placeholder findings.
"""

import json
import os
from pathlib import Path

import pytest

from app.services.report_generator import (
    _safe_filename,
    generate_csv_report,
    generate_html_report,
    generate_json_report,
    generate_report,
)

# ── Sample data fixtures ─────────────────────────────────────────────────────

SAMPLE_DATA = {
    "investigation": {
        "id": "test-inv-001",
        "name": "Test Investigation",
        "target": "example.com",
        "target_type": "domain",
        "status": "completed",
        "depth": "standard",
        "api_calls_used": 15,
        "api_budget": 100,
        "created_at": "2026-09-01T10:00:00+00:00",
        "updated_at": "2026-09-01T12:00:00+00:00",
    },
    "entities": [
        {
            "id": "domain:example.com",
            "type": "Domain",
            "value": "example.com",
            "confidence": 0.95,
            "first_seen": "2026-09-01T10:00:00+00:00",
            "last_seen": "2026-09-01T12:00:00+00:00",
            "source_count": 3,
            "properties": {},
        },
        {
            "id": "ip:93.184.216.34",
            "type": "IP",
            "value": "93.184.216.34",
            "confidence": 0.90,
            "first_seen": "2026-09-01T10:05:00+00:00",
            "last_seen": "2026-09-01T11:30:00+00:00",
            "source_count": 2,
            "properties": {"asn": "AS15169"},
        },
        {
            "id": "email:admin@example.com",
            "type": "Email",
            "value": "admin@example.com",
            "confidence": 0.80,
            "first_seen": "2026-09-01T10:10:00+00:00",
            "last_seen": None,
            "source_count": 1,
            "properties": {},
        },
    ],
    "observations": [
        {
            "id": "obs-001",
            "source_adapter": "dns",
            "source_version": "1.0.0",
            "collected_at": "2026-09-01T10:00:00+00:00",
            "method": "A record lookup",
            "target": "example.com",
            "raw_response": {"answers": [{"type": "A", "data": "93.184.216.34"}]},
            "normalized_value": "93.184.216.34",
            "confidence": 0.95,
            "status": "success",
        },
        {
            "id": "obs-002",
            "source_adapter": "whois",
            "source_version": "1.0.0",
            "collected_at": "2026-09-01T10:02:00+00:00",
            "method": "WHOIS lookup",
            "target": "example.com",
            "raw_response": {
                "registrar": "Example Registrar",
                "registrant_email": "admin@example.com",
            },
            "normalized_value": "admin@example.com",
            "confidence": 0.85,
            "status": "success",
        },
    ],
    "relationships": [
        {
            "id": "rel-001",
            "source": "domain:example.com",
            "target": "ip:93.184.216.34",
            "type": "hosted_on",
            "confidence": 0.95,
            "evidence": ["obs-001"],
            "discovered_at": "2026-09-01T10:05:00+00:00",
            "method": "dns_a_record",
        },
    ],
    "activity_log": [
        {
            "id": 1,
            "event_type": "investigation_started",
            "details": {"target": "example.com"},
            "created_at": "2026-09-01T10:00:00+00:00",
        },
    ],
    "ai_analysis": {
        "summary": (
            "This domain is hosted on a shared hosting provider with moderate"
            " threat indicators."
        ),
        "risk_level": "medium",
        "risk_reasoning": "Shared hosting with limited reputation data.",
        "key_findings": [
            {
                "title": "Domain hosted on shared infrastructure",
                "description": "IP 93.184.216.34 hosts multiple domains.",
                "entity_ids": ["domain:example.com", "ip:93.184.216.34"],
                "confidence": 0.85,
            }
        ],
        "recommendations": ["Investigate related domains on same IP"],
    },
    "generated_at": "2026-09-01T13:00:00+00:00",
}


# ── Tests for report_generator ───────────────────────────────────────────────


class TestSafeFilename:
    """Test filename sanitization."""

    def test_normal_name(self):
        assert _safe_filename("test") == "test"

    def test_strips_special_chars(self):
        result = _safe_filename('test<>:"/\\|?*name')
        assert "<" not in result
        assert ">" not in result
        assert "/" not in result
        assert "\\" not in result

    def test_empty_returns_default(self):
        assert _safe_filename("") == "report"

    def test_truncates_long_names(self):
        result = _safe_filename("a" * 200)
        assert len(result) <= 80


class TestGenerateHtmlReport:
    """Test HTML report generation."""

    def test_generates_html_file(self):
        path = generate_html_report(SAMPLE_DATA)
        assert os.path.isfile(path)
        assert path.endswith(".html")

        content = Path(path).read_text(encoding="utf-8")
        assert "Test Investigation" in content
        assert "example.com" in content
        assert "domain:example.com" in content
        assert "hosted_on" in content
        assert "AI-Assisted" in content

    def test_html_contains_evidence_provenance(self):
        path = generate_html_report(SAMPLE_DATA)
        content = Path(path).read_text(encoding="utf-8")
        assert "dns" in content
        assert "whois" in content
        assert "A record lookup" in content

    def test_html_escapes_special_chars(self):
        data = {**SAMPLE_DATA, "investigation": {
            **SAMPLE_DATA["investigation"],
            "name": 'Test <script>alert("xss")</script>',
        }}
        path = generate_html_report(data)
        content = Path(path).read_text(encoding="utf-8")
        assert "<script>" not in content


class TestGenerateJsonReport:
    """Test JSON report generation."""

    def test_generates_json_file(self):
        path = generate_json_report(SAMPLE_DATA)
        assert os.path.isfile(path)
        assert path.endswith(".json")

        with open(path, encoding="utf-8") as f:
            report = json.load(f)

        assert report["report_type"] == "osint_nexus_investigation"
        assert report["investigation"]["target"] == "example.com"
        assert len(report["entities"]) == 3
        assert len(report["observations"]) == 2
        assert len(report["relationships"]) == 1
        assert report["summary"]["entity_count"] == 3

    def test_json_preserves_all_data(self):
        path = generate_json_report(SAMPLE_DATA)
        with open(path, encoding="utf-8") as f:
            report = json.load(f)

        assert report["ai_analysis"]["risk_level"] == "medium"
        assert len(report["ai_analysis"]["key_findings"]) == 1
        assert len(report["activity_log"]) == 1


class TestGenerateCsvReport:
    """Test CSV report generation."""

    def test_generates_csv_files(self):
        path = generate_csv_report(SAMPLE_DATA)
        assert os.path.isfile(path)
        assert "entities.csv" in path

        content = Path(path).read_text(encoding="utf-8")
        assert "id,type,value,confidence" in content
        assert "domain:example.com" in content
        assert "ip:93.184.216.34" in content

    def test_csv_observations_file_also_created(self):
        path = generate_csv_report(SAMPLE_DATA)
        obs_path = path.replace("_entities.csv", "_observations.csv")
        assert os.path.isfile(obs_path)

        content = Path(obs_path).read_text(encoding="utf-8")
        assert "source_adapter" in content
        assert "dns" in content


class TestGenerateReportDispatch:
    """Test format dispatch."""

    def test_html_dispatch(self):
        path = generate_report(SAMPLE_DATA, "html")
        assert path.endswith(".html")

    def test_json_dispatch(self):
        path = generate_report(SAMPLE_DATA, "json")
        assert path.endswith(".json")

    def test_csv_dispatch(self):
        path = generate_report(SAMPLE_DATA, "csv")
        assert "entities.csv" in path

    def test_unsupported_format_raises(self):
        with pytest.raises(ValueError, match="Unsupported report format"):
            generate_report(SAMPLE_DATA, "xlsx")


class TestReportDataWithoutAi:
    """Test report data with no AI analysis."""

    def test_handles_none_ai_analysis(self):
        data = {**SAMPLE_DATA, "ai_analysis": None}
        path = generate_html_report(data)
        content = Path(path).read_text(encoding="utf-8")
        assert "Test Investigation" in content
        # Should still render without error
        assert os.path.isfile(path)

    def test_handles_empty_entities(self):
        data = {**SAMPLE_DATA, "entities": [], "observations": [], "relationships": []}
        path = generate_html_report(data)
        content = Path(path).read_text(encoding="utf-8")
        assert "No entities discovered" in content
