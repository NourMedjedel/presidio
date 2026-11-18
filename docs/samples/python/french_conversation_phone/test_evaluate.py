"""Validate the evaluator's metrics, source/data pins and public workflow."""

import hashlib
import json

import pytest
from evaluate import (
    evaluate,
    freeze_candidate,
    load_cases,
    score_predictions,
    summarize,
)


@pytest.fixture
def tiny_fixtures(tmp_path):
    """Make separate synthetic evaluator-test fixtures, never the release file."""
    directory = tmp_path / "fixtures"
    directory.mkdir()
    text = (
        "AGENT: Quel est votre numéro de téléphone ?\n"
        "CLIENT: zéro six douze trente-quatre cinquante-six soixante-dix-huit."
    )
    start = text.index("zéro")
    rows = {
        "development.jsonl": [
            {
                "id": "test-positive",
                "family": "test-spoken",
                "text": text,
                "expected_spans": [[start, len(text) - 1]],
            }
        ],
        "release.jsonl": [
            {
                "id": "test-negative",
                "family": "test-price",
                "text": "CLIENT: trente-quatre euros.",
                "expected_spans": [],
            }
        ],
    }
    manifest = {"files": {}}
    for name, cases in rows.items():
        data = "".join(
            json.dumps(case, ensure_ascii=False) + "\n" for case in cases
        ).encode()
        (directory / name).write_bytes(data)
        manifest["files"][name] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "conversations": len(cases),
        }
    (directory / "manifest.json").write_text(json.dumps(manifest))
    return directory


def test_shifted_span_counts_as_both_a_false_positive_and_a_miss():
    """Partial overlap must not earn exact-span credit."""
    expected = [("PHONE_NUMBER", 10, 20)]
    actual = [("PHONE_NUMBER", 10, 19)]
    assert score_predictions(expected, actual) == {
        "tp": 0,
        "fp": 1,
        "fn": 1,
        "exact": False,
        "missing": expected,
        "surplus": actual,
    }


def test_duplicate_predictions_do_not_inflate_scores():
    """A duplicate span contributes once, while an extra unrelated span is an FP."""
    match = ("PHONE_NUMBER", 1, 4)
    result = score_predictions([match], [match, match, ("PHONE_NUMBER", 8, 10)])
    assert (result["tp"], result["fp"], result["fn"]) == (1, 1, 0)


def test_disjoint_spans_cannot_be_replaced_by_one_merged_span():
    """A result spanning an agent turn is one FP and two missed true spans."""
    result = score_predictions(
        [("PHONE_NUMBER", 1, 4), ("PHONE_NUMBER", 10, 14)], [("PHONE_NUMBER", 1, 14)]
    )
    assert (result["tp"], result["fp"], result["fn"]) == (0, 1, 2)


def test_empty_precision_and_recall_are_undefined_not_inflated():
    """An all-negative subset has no precision/recall denominator."""
    row = {
        **score_predictions([], []),
        "redaction_exact": True,
        "output_withheld": False,
        "expected_spans": [],
    }
    result = summarize([row])
    assert result["precision"] is None
    assert result["recall"] is None
    assert result["conversation_exact_rate"] == 1.0
    assert result["redaction_exact_rate"] == 1.0
    assert summarize([])["redaction_exact_rate"] is None


def test_public_evaluation_records_misses_and_real_anonymizer_results(
    tmp_path, tiny_fixtures
):
    """The evaluator preserves baseline misses and measures actual redaction."""
    candidate = tmp_path / "candidate.json"
    pins = freeze_candidate(candidate, tiny_fixtures, repetitions=1)
    assert pins["threshold"] == 0.35
    report = evaluate(candidate, tiny_fixtures)
    core = report["measurements"]["core"]
    french = report["measurements"]["core_plus_french"]
    assert core["failures"] == ["test-positive"]
    assert core["total"]["fn"] == 1
    assert french["failures"] == []
    assert french["total"]["tp"] == 1
    assert french["total"]["redaction_exact"] == 2
    assert french["warm_recognition"]["samples"] == 2
    assert report["stress_checks_passed"] is True
    assert len(report["stress"]) == 4
    encoded = json.dumps(report)
    assert "zéro six" not in encoded
    assert "0612345678" not in encoded


def test_changed_source_pin_is_rejected(tmp_path, tiny_fixtures):
    """Do not publish results under a candidate whose source hash differs."""
    candidate = tmp_path / "candidate.json"
    pins = freeze_candidate(candidate, tiny_fixtures, repetitions=1)
    pins["sources"][next(iter(pins["sources"]))] = "0" * 64
    candidate.write_text(json.dumps(pins))
    with pytest.raises(ValueError, match="^Pinned source changed;"):
        evaluate(candidate, tiny_fixtures)


def test_changed_fixture_is_rejected_before_predictions(tmp_path, tiny_fixtures):
    """Data changes require a new pinned corpus and retained previous results."""
    candidate = tmp_path / "candidate.json"
    freeze_candidate(candidate, tiny_fixtures, repetitions=1)
    with (tiny_fixtures / "release.jsonl").open("a") as output:
        output.write("\n")
    with pytest.raises(ValueError, match="^Pinned fixtures changed;"):
        evaluate(candidate, tiny_fixtures)
    with pytest.raises(ValueError, match="^Fixture hash or size"):
        load_cases(tiny_fixtures)


@pytest.mark.parametrize("repetitions", [0, 21])
def test_invalid_timing_budget_is_rejected(tmp_path, tiny_fixtures, repetitions):
    """The evaluator cannot request an unbounded timing loop."""
    with pytest.raises(
        ValueError, match="^Timing repetitions must be between 1 and 20"
    ):
        freeze_candidate(tmp_path / "candidate.json", tiny_fixtures, repetitions)


def test_candidate_manifests_are_not_overwritten(tmp_path, tiny_fixtures):
    """Preserve the previous candidate instead of silently replacing it."""
    candidate = tmp_path / "candidate.json"
    freeze_candidate(candidate, tiny_fixtures, repetitions=1)
    before = candidate.read_bytes()
    with pytest.raises(FileExistsError):
        freeze_candidate(candidate, tiny_fixtures, repetitions=1)
    assert candidate.read_bytes() == before
