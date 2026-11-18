"""Exercise public Analyzer/Anonymizer APIs and the review-output gate."""

import subprocess
import sys
from pathlib import Path

import pytest
from redact import redact_transcript

PROMPT = "AGENT: Quel est votre numéro de téléphone ?\n"
ANSWER = "zéro six, douze, trente-quatre, cinquante-six, soixante-dix-huit"


def test_split_answer_redaction_preserves_agent_turn():
    """Replace both source fragments, never their intervening speaker turn."""
    text = (
        PROMPT + "CLIENT: zéro six, douze, trente-quatre\nAGENT: Oui.\n"
        "CLIENT: cinquante-six, soixante-dix-huit."
    )
    result = redact_transcript(text)
    assert result.review_spans == ()
    assert (
        result.redacted_text
        == PROMPT + "CLIENT: <PHONE_NUMBER>\nAGENT: Oui.\nCLIENT: <PHONE_NUMBER>."
    )


def test_international_redaction_removes_the_plus_with_the_number():
    """The combined registry must not leave a leading plus in the output."""
    result = redact_transcript(PROMPT + "CLIENT: +33 6 12 34 56 78.")
    assert result.redacted_text == PROMPT + "CLIENT: <PHONE_NUMBER>."


def test_written_number_without_prompt_retains_generic_core_detection():
    """The additive sample retains written-phone detection outside a prompt."""
    result = redact_transcript("Contact : 06 12 34 56 78.")
    assert result.redacted_text == "Contact : <PHONE_NUMBER>."


@pytest.mark.parametrize(
    "answer", ["zéro six", "0000000000", "06 12 34 56 78, non, 07 12 34 56 78"]
)
def test_review_candidates_withhold_output_even_if_core_can_detect_digits(answer):
    """A core score of 0.4 must not hide a correction requiring human review."""
    result = redact_transcript(PROMPT + "CLIENT: " + answer)
    assert result.redacted_text is None
    assert result.review_spans
    assert all(
        0 <= start < end <= len(PROMPT + "CLIENT: " + answer)
        for start, end in result.review_spans
    )


def test_no_sensitive_match_keeps_original_text():
    """Ordinary quantities must not be redacted as phone answers."""
    text = "AGENT: Combien de personnes ?\nCLIENT: trente-quatre."
    assert redact_transcript(text).redacted_text == text


@pytest.mark.parametrize(
    "scenario,marker",
    [("split", "<PHONE_NUMBER>"), ("correction", "transcript output withheld")],
)
def test_documented_demo_emits_only_redacted_or_withheld_output(scenario, marker):
    """The CLI never prints the synthetic phone values or their spoken words."""
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("redact.py")),
            "--scenario",
            scenario,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert marker in result.stdout
    assert "06 12" not in result.stdout
    assert "07 12" not in result.stdout
    assert "zéro six" not in result.stdout


def test_oversized_input_is_rejected_before_redaction():
    """The workflow uses the recognizer's bounded public interface first."""
    with pytest.raises(ValueError, match="^Transcript exceeds the character limit.$"):
        redact_transcript("x" * 100001)
