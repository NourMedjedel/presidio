"""Reproduce the eight-case French phone baseline, without an NLP model."""

import argparse
import importlib.metadata
import json
import platform
from pathlib import Path
from typing import List, Optional

import phonenumbers
from presidio_analyzer import AnalyzerEngine, EntityRecognizer, RecognizerRegistry
from presidio_analyzer.nlp_engine import NoOpNlpEngine
from presidio_analyzer.predefined_recognizers import PhoneRecognizer

REFERENCE = Path(__file__).with_name("baseline-results.json")


def valid_french_phone(digits: str) -> bool:
    """Check French numbering-plan validity, not ownership or reachability.

    :param digits: The candidate phone string.
    :return: Whether phonenumbers accepts the string for region FR.
    """
    try:
        number = phonenumbers.parse(digits, "FR")
    except phonenumbers.NumberParseException:
        return False
    return phonenumbers.is_valid_number_for_region(number, "FR")


def create_analyzer(extra: Optional[EntityRecognizer] = None) -> AnalyzerEngine:
    """Build the model-free French baseline with explicit language and region.

    :param extra: Optional opt-in recognizer to compare with the core baseline.
    :return: An analyzer at threshold 0.35, with no NER/token/lemma model.
    """
    registry = RecognizerRegistry(supported_languages=["fr"])
    registry.add_recognizer(
        PhoneRecognizer(
            supported_language="fr",
            supported_regions=("FR",),
            context=["téléphone", "portable", "mobile"],
        )
    )
    if extra is not None:
        registry.add_recognizer(extra)
    return AnalyzerEngine(
        registry=registry,
        supported_languages=["fr"],
        nlp_engine=NoOpNlpEngine(models=[{"lang_code": "fr", "model_name": "none"}]),
        default_score_threshold=0.35,
    )


def measure(analyzer: AnalyzerEngine) -> List[dict]:
    """Measure exact spans and scores on the fixed synthetic probe cases.

    :param analyzer: The configured analyzer to evaluate.
    :return: Case IDs, expected/predicted spans, scores and exact-match outcomes.
        Raw transcript values are not included in the returned report.
    """
    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    rows = []
    for case in reference["cases"]:
        results = sorted(
            analyzer.analyze(
                case["synthetic_transcript"], language="fr", entities=["PHONE_NUMBER"]
            ),
            key=lambda result: (result.start, result.end),
        )
        spans = [[result.start, result.end] for result in results]
        rows.append(
            {
                "id": case["id"],
                "expected_spans": case["expected_spans"],
                "spans": spans,
                "scores": [result.score for result in results],
                "pass": spans == case["expected_spans"],
            }
        )
    return rows


def main() -> None:
    """Print model-free baseline measurements and dependency versions."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(
        json.dumps(
            {
                "python": platform.python_version(),
                "versions": {
                    name: importlib.metadata.version(name)
                    for name in ("presidio-analyzer", "phonenumbers", "spacy")
                },
                "language": "fr",
                "region": "FR",
                "threshold": 0.35,
                "nlp": "NoOpNlpEngine; no NER/token/lemma model",
                "cases": measure(create_analyzer()),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
