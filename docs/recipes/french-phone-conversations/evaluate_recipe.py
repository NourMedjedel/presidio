"""Compare exact-span precision, recall, F2 and mean recognition latency."""

import argparse
import hashlib
import json
import statistics
import time
from pathlib import Path

from configure import configured_analyzers
from evaluate import load_cases, score_predictions


def metrics(tp: int, fp: int, fn: int, latencies: list[float]) -> dict:
    """Compute micro exact-span metrics and mean measured recognition latency.

    :param tp: Correct entity/start/end triples.
    :param fp: Extra or shifted predictions.
    :param fn: Missing or shifted expected spans.
    :param latencies: Milliseconds for one analysis call per sample, excluding
        imports, construction, data I/O, metrics and anonymization.
    :return: Counts, precision, recall, recall-weighted F2 and mean latency.
        A metric without a denominator is None, never an artificial perfect score.
    """
    denominator = 5 * tp + 4 * fn + fp
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "f2_exact_span": 5 * tp / denominator if denominator else None,
        "mean_recognition_ms": statistics.mean(latencies) if latencies else None,
        "samples": len(latencies),
    }


def evaluate_data(directory: Path) -> dict:
    """Evaluate generated, manifest-verified cases using configure.py's factories.

    :param directory: Generated fixture directory with both splits and manifest.
    :return: Metrics and every failed case's missing/surplus spans, without text.
    """
    cases = load_cases(directory)
    comparison = {}
    for name, analyzer in configured_analyzers().items():
        tp = fp = fn = 0
        durations, failures = [], []
        for case in cases:
            started = time.perf_counter_ns()
            results = analyzer.analyze(
                case["text"],
                language="fr",
                entities=["PHONE_NUMBER"],
                score_threshold=0.35,
            )
            durations.append((time.perf_counter_ns() - started) / 1_000_000)
            expected = [
                ("PHONE_NUMBER", start, end) for start, end in case["expected_spans"]
            ]
            predicted = [(r.entity_type, r.start, r.end) for r in results]
            score = score_predictions(expected, predicted)
            tp += score["tp"]
            fp += score["fp"]
            fn += score["fn"]
            if not score["exact"]:
                failures.append(
                    {
                        "id": case["id"],
                        "missing": score["missing"],
                        "surplus": score["surplus"],
                    }
                )
        comparison[name] = {**metrics(tp, fp, fn, durations), "failures": failures}
    return {
        "mode": "fresh_recipe_evaluation",
        "configuration": (
            "fr/FR, threshold 0.35, NoOpNlpEngine; exact triples, no partial credit"
        ),
        "latency_protocol": (
            "One analysis per sample after construction; mean includes the first "
            "request and excludes imports, construction and anonymization. "
            "Not warm p95 or an SLA."
        ),
        "conversations": len(cases),
        "provenance": (
            "The default generated v1 corpus is project-authored and synthetic, "
            "with 20 mobile values and known probe overlap. It is not independent "
            "or production validation. Other data require their own provenance."
        ),
        "data_sha256": {
            name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
            for name in ("manifest.json", "development.jsonl", "release.jsonl")
        },
        "metrics": comparison,
    }


def summarize_saved_report(path: Path) -> dict:
    """Derive recipe metrics from saved v1 counts/timings without new predictions.

    :param path: The existing full evaluation JSON report.
    :return: F2 and first-pass mean latency with the source report's checksum.
        The original report and its timing/quality records are not modified.
    """
    data = path.read_bytes()
    original = json.loads(data)
    comparison = {}
    for name, result in original["measurements"].items():
        totals = result["total"]
        durations = [row["first_recognition_ms"] for row in result["cases"]]
        comparison[name] = metrics(totals["tp"], totals["fp"], totals["fn"], durations)
    return {
        "mode": "derived_from_saved_evaluation",
        "source_report_sha256": hashlib.sha256(data).hexdigest(),
        "source_commit": original["candidate"]["source_commit"],
        "latency_protocol": (
            "Mean of saved first_recognition_ms per case, not the separate warm "
            "timing passes. No new predictions or timing run."
        ),
        "provenance": original["provenance"],
        "metrics": comparison,
    }


def main() -> None:
    """Run the recipe or summarize a saved report, preserving existing outputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--data", type=Path)
    source.add_argument("--saved-report", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output and args.output.exists():
        parser.error("Output exists; choose a new path to preserve previous results.")
    report = (
        evaluate_data(args.data)
        if args.data
        else summarize_saved_report(args.saved_report)
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as output:
            json.dump(report, output, indent=2)
            output.write("\n")
    print(
        json.dumps(
            {
                name: {k: v for k, v in result.items() if k != "failures"}
                for name, result in report["metrics"].items()
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
