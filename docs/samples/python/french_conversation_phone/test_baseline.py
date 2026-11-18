"""Check the public baseline configuration and reproducible measurements."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from baseline import REFERENCE, create_analyzer, measure, valid_french_phone
from presidio_analyzer import Pattern, PatternRecognizer


@pytest.mark.parametrize(
    "text,expected",
    [("0612345678", True), ("+33612345678", True), ("abc", False), ("123", False)],
)
def test_phone_validation(text, expected):
    """Numbering-plan checks do not accept arbitrary short values."""
    assert valid_french_phone(text) is expected


def test_core_baseline_reproduces_recorded_spans_and_scores():
    """French configuration reproduces successes and known misses equally."""
    reference = json.loads(REFERENCE.read_text())
    rows = measure(create_analyzer())
    assert len(rows) == 8
    for actual, case in zip(rows, reference["cases"]):
        assert actual["id"] == case["id"]
        assert actual["expected_spans"] == case["expected_spans"]
        for key in ("spans", "scores", "pass"):
            assert actual[key] == case["results"]["core"][key]


def test_optional_recognizer_is_registered_in_french():
    """The additive construction path reaches a non-default recognizer."""
    extra = PatternRecognizer(
        supported_entity="PHONE_NUMBER",
        supported_language="fr",
        patterns=[Pattern("synthetic marker", r"marqueur", 0.7)],
    )
    analyzer = create_analyzer(extra)
    [result] = analyzer.analyze("marqueur", language="fr", entities=["PHONE_NUMBER"])
    assert (result.start, result.end, result.score) == (0, 8, 0.7)


def test_baseline_command_emits_measurements_without_transcript_values():
    """The documented CLI works without an NLP-model download."""
    result = subprocess.run(
        [sys.executable, str(Path(__file__).with_name("baseline.py"))],
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(result.stdout)
    assert report["language"] == "fr"
    assert report["threshold"] == 0.35
    assert sum(row["pass"] for row in report["cases"]) == 5
    assert "synthetic_transcript" not in result.stdout
    assert "0612345678" not in result.stdout
