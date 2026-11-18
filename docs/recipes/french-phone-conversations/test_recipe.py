"""Exercise the recipe's actual generation, configuration and evaluation steps."""

import hashlib
import json
import sys

import pytest
from configure import example
from configure import main as configure_main
from evaluate_recipe import evaluate_data, metrics, summarize_saved_report
from evaluate_recipe import main as evaluate_main
from generate_data import REFERENCE, generate_data
from generate_data import main as generate_main

REPORT = REFERENCE.parent / "reports/evaluation-v1.json"


def test_generator_reproduces_every_frozen_v1_byte(tmp_path):
    """Published authoring code must reproduce annotations without detector labels."""
    output = tmp_path / "data"
    manifest = generate_data(output)
    assert sum(row["conversations"] for row in manifest["files"].values()) == 220
    for name in ("manifest.json", "development.jsonl", "release.jsonl"):
        assert (output / name).read_bytes() == (REFERENCE / name).read_bytes()
    with pytest.raises(FileExistsError):
        generate_data(output)


def test_configuration_example_uses_french_detection_and_public_redaction():
    """Core misses the spoken split answer; the additive sample returns two spans."""
    result = example()
    assert result["detections"]["core"] == []
    assert [
        (r["start"], r["end"], r["score"])
        for r in result["detections"]["core_plus_french"]
    ] == [(52, 82, 0.7), (103, 135, 0.7)]
    assert result["redacted_output"].count("<PHONE_NUMBER>") == 2
    assert "AGENT: Oui." in result["redacted_output"]
    assert result["review_spans"] == ()


def test_f2_uses_recall_weighted_exact_span_counts():
    """F2 must weight misses four times as heavily as false positives."""
    result = metrics(20, 0, 100, [1.0, 3.0])
    assert result["precision"] == 1.0
    assert result["recall"] == pytest.approx(1 / 6)
    assert result["f2_exact_span"] == 0.2
    assert result["mean_recognition_ms"] == 2.0
    assert metrics(0, 0, 0, [])["f2_exact_span"] is None
    assert metrics(0, 0, 0, [])["mean_recognition_ms"] is None


def test_saved_report_derivation_preserves_original_measurements():
    """Add the recipe metrics without overwriting or rerunning the frozen result."""
    before = hashlib.sha256(REPORT.read_bytes()).hexdigest()
    summary = summarize_saved_report(REPORT)
    assert summary["source_report_sha256"] == before
    assert summary["metrics"]["core"]["f2_exact_span"] == 0.2
    assert summary["metrics"]["core_plus_french"]["f2_exact_span"] == 1.0
    assert summary["metrics"]["core"]["samples"] == 220
    assert hashlib.sha256(REPORT.read_bytes()).hexdigest() == before


def test_generated_corpus_evaluates_through_recipe_configuration(tmp_path):
    """Run all three steps through real public APIs and preserve baseline failures."""
    data = tmp_path / "data"
    generate_data(data)
    report = evaluate_data(data)
    core, french = report["metrics"]["core"], report["metrics"]["core_plus_french"]
    assert (core["tp"], core["fp"], core["fn"], len(core["failures"])) == (
        20,
        0,
        100,
        80,
    )
    assert (french["tp"], french["fp"], french["fn"], french["failures"]) == (
        120,
        0,
        0,
        [],
    )
    assert french["f2_exact_span"] == 1.0
    assert "zéro six" not in json.dumps(report)


def test_recipe_commands_and_output_preservation(tmp_path, monkeypatch, capsys):
    """The documented commands work and refuse to silently replace prior results."""
    data, output = tmp_path / "data", tmp_path / "report.json"
    monkeypatch.setattr(sys, "argv", ["generate_data.py", str(data)])
    generate_main()
    with pytest.raises(SystemExit):
        generate_main()
    configure_main()
    monkeypatch.setattr(
        sys,
        "argv",
        ["evaluate_recipe.py", "--saved-report", str(REPORT), "--output", str(output)],
    )
    evaluate_main()
    before = output.read_bytes()
    with pytest.raises(SystemExit):
        evaluate_main()
    assert output.read_bytes() == before
    monkeypatch.setattr(sys, "argv", ["evaluate_recipe.py", "--data", str(data)])
    evaluate_main()
    captured = capsys.readouterr()
    assert "f2_exact_span" in captured.out
    assert "06 12 34" not in captured.out
