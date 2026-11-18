"""Pin and evaluate the French sample without an LLM judge or raw-value reports."""

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import re
import statistics
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from baseline import create_analyzer
from french_phone_recognizer import FrenchPhoneConversationRecognizer
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from redact import THRESHOLD, redact_transcript

REPO = Path(__file__).resolve().parents[4]
SAMPLE = Path(__file__).resolve().parent
FIXTURES = SAMPLE / "fixtures"
SOURCE_FILES = (
    "docs/samples/python/conversational_prompt_recognizer/conversational_prompt_recognizer.py",
    "docs/samples/python/french_conversation_phone/french_numbers.py",
    "docs/samples/python/french_conversation_phone/french_phone_recognizer.py",
    "docs/samples/python/french_conversation_phone/redact.py",
    "docs/samples/python/french_conversation_phone/baseline.py",
    "docs/samples/python/french_conversation_phone/evaluate.py",
    "presidio-analyzer/uv.lock",
    "presidio-anonymizer/uv.lock",
)
_SAFE_ID = re.compile(r"[a-z0-9_-]{1,80}")
_OPERATORS = {
    "PHONE_NUMBER": OperatorConfig("replace", {"new_value": "<PHONE_NUMBER>"})
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_cases(directory: Path) -> List[dict]:
    """Load hash-verified, bounded synthetic fixtures with exact annotations.

    :param directory: Directory containing manifest.json and the two JSONL splits.
    :return: Cases with their split names, original text and annotation spans.
    :raises ValueError: If hashes, identifiers, bounds or annotations are invalid.
        Errors never include case text or arbitrary user-supplied field values.
    """
    try:
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        if set(manifest["files"]) != {"development.jsonl", "release.jsonl"}:
            raise ValueError("Expected development and release splits.")
        cases, identifiers = [], set()
        for name, metadata in manifest["files"].items():
            path = directory / name
            if path.stat().st_size > 1_000_000 or _sha(path) != metadata["sha256"]:
                raise ValueError("Fixture hash or size does not match the manifest.")
            rows = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
            ]
            if not rows or len(rows) > 1000 or len(rows) != metadata["conversations"]:
                raise ValueError("Fixture count is invalid.")
            for case in rows:
                if not _SAFE_ID.fullmatch(case["id"]) or not _SAFE_ID.fullmatch(
                    case["family"]
                ):
                    raise ValueError("Case identifiers must be bounded ASCII labels.")
                if case["id"] in identifiers:
                    raise ValueError("Case identifiers must be unique across splits.")
                identifiers.add(case["id"])
                text, spans = case["text"], case["expected_spans"]
                if len(text) > 100_000 or not isinstance(spans, list):
                    raise ValueError(
                        "Case text or annotations exceed the supported format."
                    )
                previous_end = 0
                for start, end in spans:
                    if not (
                        type(start) is int
                        and type(end) is int
                        and previous_end <= start < end <= len(text)
                    ):
                        raise ValueError(
                            "Expected spans must be ordered, disjoint character ranges."
                        )
                    previous_end = end
                cases.append({**case, "split": Path(name).stem})
        return cases
    except (KeyError, TypeError, json.JSONDecodeError, UnicodeError):
        raise ValueError(
            "Fixture schema is invalid; no input text is included in this error."
        ) from None


def freeze_candidate(
    destination: Path, fixtures: Path = FIXTURES, repetitions: int = 5
) -> dict:
    """Pin committed source and corpus hashes before running predictions.

    :param destination: New candidate manifest path; existing files are preserved.
    :param fixtures: Hash-annotated synthetic fixture directory.
    :param repetitions: Timing repetitions per case, between 1 and 20.
    :return: Source/data pins, fixed protocol and source commit.
    :raises ValueError: If source is dirty, timing settings are invalid or data
        fail validation.
    :raises FileExistsError: If the candidate manifest already exists.
    """
    if not 1 <= repetitions <= 20:
        raise ValueError("Timing repetitions must be between 1 and 20.")
    load_cases(fixtures)
    subprocess.run(
        ["git", "ls-files", "--error-unmatch", *SOURCE_FILES],
        cwd=REPO,
        check=True,
        capture_output=True,
    )
    dirty = subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", *SOURCE_FILES], cwd=REPO
    )
    if dirty.returncode:
        raise ValueError("Commit pinned source changes before freezing a candidate.")
    manifest = {
        "schema_version": 1,
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
        ).strip(),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {name: _sha(REPO / name) for name in SOURCE_FILES},
        "fixtures": {
            name: _sha(fixtures / name)
            for name in ("manifest.json", "development.jsonl", "release.jsonl")
        },
        "threshold": THRESHOLD,
        "timing_repetitions": repetitions,
        "precision_target": 0.95,
        "recall_target": 0.95,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as output:
        json.dump(manifest, output, indent=2)
        output.write("\n")
    return manifest


def score_predictions(expected: list, predicted: list) -> dict:
    """Score exact entity/start/end matches, without partial-overlap credit.

    :param expected: Expected entity/start/end triples.
    :param predicted: Predicted triples; identical duplicates count once.
    :return: Counts and sorted missing/surplus triples; no matched text.
    """
    expected, predicted = set(map(tuple, expected)), set(map(tuple, predicted))
    return {
        "tp": len(expected & predicted),
        "fp": len(predicted - expected),
        "fn": len(expected - predicted),
        "exact": expected == predicted,
        "missing": sorted(expected - predicted),
        "surplus": sorted(predicted - expected),
    }


def summarize(rows: list) -> dict:
    """Aggregate case results without inflating undefined precision or recall.

    :param rows: Scored cases with redaction_exact and output_withheld flags.
    :return: Counts, exact-conversation/output rates and micro precision/recall.
    """
    tp, fp, fn = (sum(row[key] for row in rows) for key in ("tp", "fp", "fn"))
    return {
        "conversations": len(rows),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "conversations_exact": sum(row["exact"] for row in rows),
        "redaction_exact": sum(row["redaction_exact"] for row in rows),
        "conversation_exact_rate": sum(row["exact"] for row in rows) / len(rows)
        if rows
        else None,
        "redaction_exact_rate": sum(row["redaction_exact"] for row in rows) / len(rows)
        if rows
        else None,
        "output_withheld": sum(row["output_withheld"] for row in rows),
        "negative_cases_with_fp": sum(
            not row["expected_spans"] and row["fp"] > 0 for row in rows
        ),
    }


def _timings(values: list) -> dict:
    ordered = sorted(values)
    return {
        "samples": len(values),
        "median_ms": statistics.median(values),
        "p95_ms": ordered[math.ceil(len(values) * 0.95) - 1],
        "max_ms": max(values),
    }


def _expected_output(case: dict) -> str:
    parts, cursor = [], 0
    for start, end in case["expected_spans"]:
        parts.extend((case["text"][cursor:start], "<PHONE_NUMBER>"))
        cursor = end
    return "".join(parts) + case["text"][cursor:]


def _peak_rss_mib():
    try:
        import resource

        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return value / (1024 * 1024 if platform.system() == "Darwin" else 1024)
    except ImportError:
        return None


def _stress(repetitions: int) -> list:
    workloads = {
        "repeated_fillers": "AGENT: Quel est votre numéro de téléphone ?\nCLIENT: zéro"
        + " euh" * 2000
        + " six douze trente-quatre cinquante-six soixante-dix-huit",
        "near_text_limit": ("AGENT: Autre sujet.\nCLIENT: " + "x" * 9980 + "\n") * 9,
        "maximum_turns": "AGENT: Autre sujet.\n" * 1000,
        "over_text_limit": "x" * 100001,
    }
    results = []
    for name, text in workloads.items():
        durations, outcome = [], None
        for _ in range(repetitions):
            started = time.perf_counter_ns()
            try:
                result = redact_transcript(text)
                outcome = "withheld" if result.review_spans else "returned"
            except ValueError:
                outcome = "rejected"
            durations.append((time.perf_counter_ns() - started) / 1_000_000)
        expected = "rejected" if name == "over_text_limit" else "returned"
        results.append(
            {
                "id": name,
                "characters": len(text),
                "turns": len(text.splitlines()),
                "outcome": outcome,
                "expected_outcome": expected,
                "pass": outcome == expected,
                **_timings(durations),
            }
        )
    return results


def evaluate(candidate: Path, fixtures: Path = FIXTURES) -> dict:
    """Evaluate one frozen candidate and preserve all exact-span failures.

    :param candidate: Candidate manifest produced before predictions.
    :param fixtures: Fixture directory matching the candidate's data hashes.
    :return: Source/data metadata, quality, timings and resource measurements.
        Reports contain case IDs and positions, never transcript/phone values.
    :raises ValueError: If pinned code, data or fixed protocol no longer match.
    """
    pins = json.loads(candidate.read_text(encoding="utf-8"))
    if (
        set(pins["sources"]) != set(SOURCE_FILES)
        or pins["threshold"] != THRESHOLD
        or pins["precision_target"] != 0.95
        or pins["recall_target"] != 0.95
        or not 1 <= pins["timing_repetitions"] <= 20
    ):
        raise ValueError("Candidate protocol or source list is invalid.")
    for name in SOURCE_FILES:
        if _sha(REPO / name) != pins["sources"][name]:
            raise ValueError(
                "Pinned source changed; freeze a new candidate "
                "and retain previous results."
            )
    for name in ("manifest.json", "development.jsonl", "release.jsonl"):
        if _sha(fixtures / name) != pins["fixtures"][name]:
            raise ValueError(
                "Pinned fixtures changed; retain previous results "
                "and version the corpus."
            )
    cases = load_cases(fixtures)
    anonymizer = AnonymizerEngine()
    measurements = {}
    for name, recognizer in (
        ("core", None),
        ("core_plus_french", FrenchPhoneConversationRecognizer()),
    ):
        started = time.perf_counter_ns()
        analyzer = create_analyzer(recognizer)
        construction_ms = (time.perf_counter_ns() - started) / 1_000_000
        rows, latencies, workflow_latencies = [], [], []
        for case in cases:
            started = time.perf_counter_ns()
            results = analyzer.analyze(
                case["text"],
                language="fr",
                entities=["PHONE_NUMBER"],
                score_threshold=THRESHOLD,
            )
            first_ms = (time.perf_counter_ns() - started) / 1_000_000
            predictions = [(r.entity_type, r.start, r.end) for r in results]
            expected = [
                ("PHONE_NUMBER", start, end) for start, end in case["expected_spans"]
            ]
            started = time.perf_counter_ns()
            if recognizer is None:
                output = anonymizer.anonymize(case["text"], results, _OPERATORS).text
            else:
                output = redact_transcript(case["text"]).redacted_text
                workflow_latencies.append(
                    (time.perf_counter_ns() - started) / 1_000_000
                )
            rows.append(
                {
                    "id": case["id"],
                    "family": case["family"],
                    "split": case["split"],
                    "expected_spans": expected,
                    "predicted_spans": sorted(set(predictions)),
                    "scores": [r.score for r in results],
                    **score_predictions(expected, predictions),
                    "redaction_exact": output == _expected_output(case),
                    "output_withheld": output is None,
                    "first_recognition_ms": first_ms,
                }
            )
        # Timing repeats do not retry/replace quality outcomes. Both engines are
        # reused and warm; construction and the actual candidate workflow are separate.
        for _ in range(pins["timing_repetitions"]):
            for case in cases:
                started = time.perf_counter_ns()
                analyzer.analyze(
                    case["text"],
                    language="fr",
                    entities=["PHONE_NUMBER"],
                    score_threshold=THRESHOLD,
                )
                latencies.append((time.perf_counter_ns() - started) / 1_000_000)
        grouped = {}
        for split in ("development", "release"):
            selected = [row for row in rows if row["split"] == split]
            grouped[split] = {
                "total": summarize(selected),
                "by_family": {
                    family: summarize(
                        [row for row in selected if row["family"] == family]
                    )
                    for family in sorted({row["family"] for row in selected})
                },
            }
        measurements[name] = {
            "total": summarize(rows),
            "by_split": grouped,
            "construction_ms": construction_ms,
            "warm_recognition": _timings(latencies),
            "cases": rows,
            "failures": [
                row["id"]
                for row in rows
                if not row["exact"] or not row["redaction_exact"]
            ],
        }
        if workflow_latencies:
            measurements[name]["workflow_including_construction"] = _timings(
                workflow_latencies
            )
    release = measurements["core_plus_french"]["by_split"]["release"]["total"]
    targets_met = (release["precision"] or 0) >= 0.95 and (
        release["recall"] or 0
    ) >= 0.95
    stress = _stress(pins["timing_repetitions"])
    return {
        "candidate": pins,
        "candidate_manifest_sha256": _sha(candidate),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "provenance": (
            "Frozen project-authored synthetic regression cases; known "
            "families/cases overlap development probes. Not independent "
            "validation or production accuracy."
        ),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "logical_cpus": os.cpu_count(),
            "dependencies": {
                name: importlib.metadata.version(name)
                for name in (
                    "presidio-analyzer",
                    "presidio-anonymizer",
                    "phonenumbers",
                    "spacy",
                    "cryptography",
                )
            },
        },
        "protocol": (
            "fr/FR, threshold 0.35, NoOpNlpEngine, no NER/LLM. Exact spans, "
            "duplicate triples counted once, no overlap credit. P95 uses "
            "nearest rank. Warm timings exclude imports/construction; "
            "workflow includes candidate construction. Peak RSS includes "
            "the entire process, imports, both engines and stress, "
            "not incremental model memory."
        ),
        "measurements": measurements,
        "stress": stress,
        "peak_process_rss_mib": _peak_rss_mib(),
        "stress_checks_passed": all(row["pass"] for row in stress),
        "release_precision_recall_targets_met": targets_met,
        "release_ready": None,
        "release_readiness_note": (
            "Not inferred: compatibility, named regressions and remaining "
            "release gates must also be checked."
        ),
    }


def main() -> None:
    """Freeze a new candidate or write a non-overwriting evaluation report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", type=Path)
    parser.add_argument("--candidate", type=Path, default=SAMPLE / "candidate.json")
    parser.add_argument("--fixtures", type=Path, default=FIXTURES)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument(
        "--output", type=Path, default=SAMPLE / "reports" / "evaluation.json"
    )
    args = parser.parse_args()
    try:
        if args.freeze:
            freeze_candidate(args.freeze, args.fixtures, args.repetitions)
            print("Candidate frozen; no predictions run.")
            return
        if args.output.exists():
            raise FileExistsError(
                "Output exists; choose a new path to preserve previous results."
            )
        report = evaluate(args.candidate, args.fixtures)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as output:
            json.dump(report, output, indent=2)
            output.write("\n")
        print("Evaluation recorded; see report for every failure and limitation.")
    except (ValueError, FileExistsError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
