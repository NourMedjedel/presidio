"""Model-free French phone redaction, with a separate human-review gate."""

import argparse
from dataclasses import dataclass
from typing import Optional, Tuple

from baseline import create_analyzer
from french_phone_recognizer import FrenchPhoneConversationRecognizer
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

THRESHOLD = 0.35


@dataclass(frozen=True)
class RedactionOutcome:
    """An output that is withheld whenever a phone answer requires review.

    :param redacted_text: Non-reversible replacements, or None pending review.
    :param review_spans: Original end-exclusive character ranges requiring review.
        Values and normalized phone strings are deliberately omitted.
    """

    redacted_text: Optional[str]
    review_spans: Tuple[Tuple[int, int], ...] = ()


def redact_transcript(text: str) -> RedactionOutcome:
    """Redact detected phone spans, withholding output for review candidates.

    This best-effort phone-only sample does not guarantee that text is anonymous.
    Other PII types, unsupported prompts and ASR errors need additional controls.

    :param text: One bounded transcript with explicit speaker labels.
    :return: Redacted text, or review positions with no transcript output.
    :raises ValueError: If a transcript or utterance exceeds a documented limit.
    """
    recognizer = FrenchPhoneConversationRecognizer()
    # Check before AnalyzerEngine can de-duplicate a low-score review candidate
    # against a higher-score generic phone result. Input bounds run here first.
    candidates = recognizer.analyze(text, entities=["PHONE_NUMBER"])
    review = tuple((r.start, r.end) for r in candidates if r.score < THRESHOLD)
    if review:
        return RedactionOutcome(redacted_text=None, review_spans=review)

    analyzer = create_analyzer(recognizer)
    results = analyzer.analyze(
        text, language="fr", entities=["PHONE_NUMBER"], score_threshold=THRESHOLD
    )
    output = AnonymizerEngine().anonymize(
        text=text,
        analyzer_results=results,
        operators={
            "PHONE_NUMBER": OperatorConfig("replace", {"new_value": "<PHONE_NUMBER>"})
        },
    )
    return RedactionOutcome(redacted_text=output.text)


def main() -> None:
    """Run synthetic examples; never print a transcript awaiting review."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=("split", "correction"), default="split")
    args = parser.parse_args()
    # Project-authored synthetic examples only; never contact these values.
    question = "AGENT: Quel est votre numéro de téléphone ?\n"
    examples = {
        "split": question
        + (
            "CLIENT: zéro six, douze, trente-quatre\n"
            "AGENT: Oui.\n"
            "CLIENT: cinquante-six, soixante-dix-huit."
        ),
        "correction": question + "CLIENT: 06 12 34 56 78, non, 07 12 34 56 78.",
    }
    outcome = redact_transcript(examples[args.scenario])
    if outcome.review_spans:
        print("Human review required; transcript output withheld.")
        print("PHONE_NUMBER ranges:", outcome.review_spans)
    else:
        print(outcome.redacted_text)


if __name__ == "__main__":
    main()
