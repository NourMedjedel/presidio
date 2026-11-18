"""Configure the same French baseline and opt-in recognizer used by the recipe."""

import json

from baseline import create_analyzer
from french_phone_recognizer import FrenchPhoneConversationRecognizer
from presidio_analyzer import AnalyzerEngine
from redact import redact_transcript


def configured_analyzers() -> dict[str, AnalyzerEngine]:
    """Build both configurations with fr/FR, threshold 0.35 and NoOpNlpEngine.

    :return: Core baseline and core-plus-French analyzers. Shared factory code
        configures registry languages, France region and French context explicitly.
    """
    return {
        "core": create_analyzer(),
        "core_plus_french": create_analyzer(FrenchPhoneConversationRecognizer()),
    }


def example() -> dict:
    """Run one fixed synthetic split answer through detection and redaction.

    :return: Original-position detections and redacted output, without raw input.
    """
    text = (
        "AGENT: Quel est votre numéro de téléphone ?\n"
        "CLIENT: zéro six, douze, trente-quatre\nAGENT: Oui.\n"
        "CLIENT: cinquante-six, soixante-dix-huit."
    )
    detections = {}
    for name, analyzer in configured_analyzers().items():
        results = analyzer.analyze(
            text, language="fr", entities=["PHONE_NUMBER"], score_threshold=0.35
        )
        detections[name] = [
            {"entity": r.entity_type, "start": r.start, "end": r.end, "score": r.score}
            for r in sorted(results, key=lambda r: r.start)
        ]
    outcome = redact_transcript(text)
    return {
        "detections": detections,
        "redacted_output": outcome.redacted_text,
        "review_spans": outcome.review_spans,
    }


def main() -> None:
    """Print the fixed example's positions and redacted output."""
    print(json.dumps(example(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
