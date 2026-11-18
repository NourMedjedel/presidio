"""Public behavior of the opt-in French conversation recognizer."""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from baseline import create_analyzer
from conversational_prompt_recognizer import BoundedConversationPolicy
from french_phone_recognizer import (
    FrenchPhoneConversationRecognizer,
    valid_french_phone_answer,
)
from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NoOpNlpEngine
from presidio_analyzer.recognizer_registry import RecognizerRegistryProvider

PROMPT = "AGENT: Quel est votre numéro de téléphone ?\n"
ANSWER = "zéro six, douze, trente-quatre, cinquante-six, soixante-dix-huit"
OTHER = "zéro sept, douze, trente-quatre, cinquante-six, soixante-dix-huit"


def found(text, recognizer=None):
    """Return public scores and original substrings, in source order."""
    recognizer = recognizer or FrenchPhoneConversationRecognizer()
    results = recognizer.analyze(text, entities=["PHONE_NUMBER"])
    return [(r.score, text[r.start : r.end]) for r in results]


@pytest.mark.parametrize(
    "value,expected",
    [
        ("0612345678", True),
        ("+33612345678", True),
        ("612345678", False),
        ("33612345678", False),
        ("0033612345678", False),
        ("+330612345678", False),
        ("0000000000", False),
        ("+331", False),
        ("hello", False),
    ],
)
def test_explicit_french_phone_forms(value, expected):
    """Do not repair a missing zero or implicit international prefix."""
    assert valid_french_phone_answer(value) is expected


@pytest.mark.parametrize(
    "prompt",
    [
        "Quel est votre numéro de téléphone ?",
        "Quel est votre numero de portable ?",
        "Pouvez-vous me donner votre numéro de mobile ?",
        "Pouvez vous indiquer votre numéro de téléphone ?",
        "Indiquez votre numéro de téléphone.",
        "Donnez-moi votre numéro de téléphone.",
    ],
)
def test_supported_phone_prompts(prompt):
    """Only declared requesting forms arm the next answer."""
    assert found("CONSEILLER: " + prompt + "\nUTILISATEUR: " + ANSWER + ".") == [
        (0.7, ANSWER)
    ]


@pytest.mark.parametrize(
    "prefix",
    [
        "",
        "AGENT: Combien de participants ?\n",
        "AGENT: Quel est le prix ?\n",
        "AGENT: Quel est votre numéro de commande ?\n",
        "AGENT: Ne donnez pas votre numéro de téléphone.\n",
        "AGENT: Le formulaire dit « Quel est votre numéro de téléphone ? »\n",
        PROMPT + "AGENT: Combien de participants ?\n",
        PROMPT + "TIERS: Bonjour.\n",
        PROMPT + "unparsed line\n",
        PROMPT + "\n",
    ],
)
def test_nonphone_prompts_and_boundaries_do_not_arm_answer(prefix):
    """A phone-shaped spoken number needs a live phone prompt."""
    assert found(prefix + "CLIENT: " + ANSWER) == []


def test_split_answer_has_exact_disjoint_spans():
    """Three answer turns fit within five turns, without spanning acknowledgements."""
    parts = ["zéro six", "douze, trente-quatre", "cinquante-six, soixante-dix-huit"]
    text = PROMPT + "\n".join(
        [
            "CLIENT: " + parts[0],
            "AGENT: OUI !",
            "CLIENT: " + parts[1],
            "AGENT: D’accord.",
            "CLIENT: " + parts[2] + ".",
        ]
    )
    assert found(text) == [(0.7, part) for part in parts]
    results = FrenchPhoneConversationRecognizer().analyze(
        text, entities=["PHONE_NUMBER"]
    )
    assert [(r.start, r.end) for r in results] == [
        (text.index(p), text.index(p) + len(p)) for p in parts
    ]


@pytest.mark.parametrize(
    "boundary",
    [
        "AGENT: Autre question ?",
        "TIERS: Oui.",
        "raw line",
        "",
        "UTILISATEUR: trente-quatre",
    ],
)
def test_partial_answer_does_not_join_across_boundaries(boundary):
    """Keep the partial candidate for review; do not borrow another speaker's digits."""
    text = (
        PROMPT
        + "CLIENT: zéro six, douze\n"
        + boundary
        + "\nCLIENT: trente-quatre, cinquante-six, soixante-dix-huit"
    )
    assert found(text) == [(0.2, "zéro six, douze")]


def test_phone_prompt_is_consumed_by_empty_answer():
    """An empty/non-numeric answer cannot leave a phone prompt armed."""
    assert found(PROMPT + "CLIENT: Je ne sais pas.\nCLIENT: " + ANSWER) == []


def test_new_prompt_allows_explicit_retry():
    """The next question is processed after a partial answer is closed."""
    text = PROMPT + "CLIENT: zéro six\n" + PROMPT + "CLIENT: " + ANSWER
    assert found(text) == [(0.2, "zéro six"), (0.7, ANSWER)]


def test_valid_answer_does_not_consume_next_unprompted_number():
    """Only correction markers reopen a complete answer within its bounds."""
    assert found(PROMPT + "CLIENT: " + ANSWER + "\nCLIENT: " + OTHER) == [(0.7, ANSWER)]


@pytest.mark.parametrize(
    "answer",
    [
        "zéro six",
        "612345678",
        "0033612345678",
        "33612345678",
        "0000000000",
        "+33 (0) 6 12 34 56 78",
    ],
)
def test_incomplete_and_invalid_answers_require_review(answer):
    """Preserve invalid candidates instead of guessing a valid phone."""
    results = FrenchPhoneConversationRecognizer().analyze(
        PROMPT + "CLIENT: " + answer, entities=["PHONE_NUMBER"]
    )
    assert results
    assert all(r.score == 0.2 for r in results)
    assert all(
        "human review required" in r.analysis_explanation.textual_explanation
        for r in results
    )


def test_correction_in_same_turn_keeps_both_candidates_for_review():
    """A second phone candidate never silently replaces the first."""
    text = PROMPT + "CLIENT: " + ANSWER + ", non, je corrige : " + OTHER + "."
    assert found(text) == [(0.2, ANSWER), (0.2, OTHER)]


def test_correction_in_later_turn_downgrades_both_candidates():
    """A correction in the bounded same-customer answer marks both versions."""
    text = (
        PROMPT
        + "CLIENT: "
        + ANSWER
        + "\nAGENT: Je vous écoute.\nCLIENT: Pardon, "
        + OTHER
    )
    assert found(text) == [(0.2, ANSWER), (0.2, OTHER)]


def test_withdrawn_answer_without_replacement_still_requires_review():
    """A correction with no replacement must not leave the old answer validated."""
    text = PROMPT + "CLIENT: " + ANSWER + "\nCLIENT: Pardon, ce n’est pas le bon."
    assert found(text) == [(0.2, ANSWER)]


def test_explicit_cancellation_withdraws_the_previous_answer():
    """Cancellation must not leave a previously complete answer validated."""
    text = PROMPT + "CLIENT: " + ANSWER + "\nCLIENT: Annulez cette réponse."
    assert found(text) == [(0.2, ANSWER)]


def test_explicit_cancellation_consumes_the_prompt():
    """A cancelled request requires another phone prompt before a later answer."""
    assert found(PROMPT + "CLIENT: Annulez.\nCLIENT: " + ANSWER) == []


def test_repeated_fillers_remain_bounded_and_preserve_redaction_span():
    """Long allowed filler sequences do not prevent exact original spans."""
    answer = (
        "zéro"
        + " euh" * 1000
        + " six douze trente-quatre cinquante-six soixante-dix-huit"
    )
    assert found(PROMPT + "CLIENT: " + answer + ".") == [(0.7, answer)]


def test_prompt_cannot_stay_armed_through_unbounded_acknowledgements():
    """The pending prompt also expires within the configured turn budget."""
    assert found(PROMPT + "AGENT: Oui.\n" * 6 + "CLIENT: " + ANSWER) == []


def test_ambiguous_runs_are_not_joined_through_unknown_words():
    """Keep unknown text outside candidate spans and request review."""
    assert found(PROMPT + "CLIENT: zéro six puis douze") == [
        (0.2, "zéro six"),
        (0.2, "douze"),
    ]


@pytest.mark.parametrize(
    "answer", ["++33612345678", "0612345678+99", "+33612345678+99"]
)
def test_malformed_plus_sequences_are_reviewed_without_partial_validation(answer):
    """Do not validate a convenient substring of a malformed numeric answer."""
    results = found(PROMPT + "CLIENT: " + answer)
    assert results
    assert all(score == 0.2 for score, _ in results)


def test_answer_turn_limit_stops_before_fourth_fragment():
    """A fourth answering turn cannot complete an otherwise short answer."""
    text = (
        PROMPT + "CLIENT: zéro\nCLIENT: six\nCLIENT: douze\n"
        "CLIENT: trente-quatre cinquante-six soixante-dix-huit"
    )
    assert found(text) == [(0.2, "zéro"), (0.2, "six"), (0.2, "douze")]


def test_total_turn_limit_includes_backchannels():
    """Backchannels cannot extend a partial answer indefinitely."""
    text = (
        PROMPT
        + "CLIENT: zéro six\n"
        + "AGENT: Oui.\n" * 4
        + "CLIENT: douze trente-quatre cinquante-six soixante-dix-huit"
    )
    assert found(text) == [(0.2, "zéro six")]


def test_crlf_and_unicode_prose_preserve_original_offsets():
    """Source offsets are Python characters, unaffected by CRLF or emoji prefixes."""
    text = PROMPT.replace("\n", "\r\n") + "CLIENT: 👋 C’est le " + ANSWER + ".\r\n"
    [result] = FrenchPhoneConversationRecognizer(name="French sample").analyze(
        text, entities=["PHONE_NUMBER"]
    )
    assert (result.start, result.end, result.score) == (
        text.index(ANSWER),
        text.index(ANSWER) + len(ANSWER),
        0.7,
    )
    assert result.analysis_explanation.recognizer == "French sample"
    assert ANSWER not in result.analysis_explanation.textual_explanation


def test_registry_combination_returns_one_international_span_including_plus():
    """The opt-in recognizer and core recognizer agree on the original +33 span."""
    answer = "+33 6 12 34 56 78"
    text = PROMPT + "CLIENT: " + answer + "."
    [result] = create_analyzer(FrenchPhoneConversationRecognizer()).analyze(
        text, language="fr", entities=["PHONE_NUMBER"], return_decision_process=True
    )
    assert (result.start, result.end, result.score) == (
        text.index(answer),
        text.index(answer) + len(answer),
        0.7,
    )


def test_development_conversations_match_exact_expected_spans():
    """Use development only; release cases remain unevaluated at this step."""
    cases = Path(__file__).with_name("fixtures") / "development.jsonl"
    analyzer = create_analyzer(FrenchPhoneConversationRecognizer())
    for line in cases.read_text().splitlines():
        case = json.loads(line)
        results = sorted(
            analyzer.analyze(case["text"], language="fr", entities=["PHONE_NUMBER"]),
            key=lambda r: r.start,
        )
        assert [[r.start, r.end] for r in results] == case["expected_spans"], case["id"]


def test_one_recognizer_is_isolated_between_requests_and_threads():
    """A prompt in one transcript must never affect another request."""
    recognizer = FrenchPhoneConversationRecognizer()
    texts = [
        PROMPT,
        "CLIENT: " + ANSWER,
        PROMPT + "CLIENT: " + ANSWER,
        "CLIENT: " + OTHER,
    ] * 4
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda text: found(text, recognizer), texts))
    assert results == [[], [], [(0.7, ANSWER)], []] * 4


def test_entities_filter_is_honored():
    """Entity filtering applies at the public recognizer boundary."""
    assert (
        FrenchPhoneConversationRecognizer().analyze(
            PROMPT + "CLIENT: " + ANSWER, entities=["CREDIT_CARD"]
        )
        == []
    )


@pytest.mark.parametrize(
    "text,error",
    [
        ("x" * 100001, "Transcript exceeds the character limit."),
        ("x\n" * 1001, "Transcript exceeds the turn limit."),
        ("CLIENT: " + "x" * 10001, "Utterance exceeds the character limit."),
    ],
)
def test_input_bounds_have_generic_errors(text, error):
    """Reject excess input without echoing the submitted data."""
    with pytest.raises(ValueError) as exc:
        FrenchPhoneConversationRecognizer().analyze(text, entities=["PHONE_NUMBER"])
    assert str(exc.value) == error


def test_nonpositive_policy_limit_is_rejected():
    """Custom policy bounds must be positive."""
    with pytest.raises(ValueError, match=r"^Conversation limits must be positive\.$"):
        BoundedConversationPolicy(max_answer_turns=0)


def test_french_registry_loaded_from_yaml_accepts_explicit_custom_sample(tmp_path):
    """Load core YAML through the provider, then register the custom Python sample."""
    config = tmp_path / "recognizers.yaml"
    config.write_text(
        "supported_languages: [fr]\nrecognizers:\n  - name: PhoneRecognizer\n"
        "    supported_languages: [fr]\n    type: predefined\n    enabled: true\n"
    )
    registry = RecognizerRegistryProvider(conf_file=config).create_recognizer_registry()
    registry.add_recognizer(FrenchPhoneConversationRecognizer())
    engine = AnalyzerEngine(
        registry=registry,
        supported_languages=["fr"],
        nlp_engine=NoOpNlpEngine(models=[{"lang_code": "fr", "model_name": "none"}]),
    )
    [result] = engine.analyze(
        PROMPT + "CLIENT: " + ANSWER, language="fr", entities=["PHONE_NUMBER"]
    )
    assert result.score == 0.7
    assert result.start == len(PROMPT + "CLIENT: ")
