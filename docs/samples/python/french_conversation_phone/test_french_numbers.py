"""Public-boundary tests for the French number-normalization sample."""

import hashlib
import json
from pathlib import Path

import pytest
from french_numbers import MAX_UTTERANCE_LENGTH, normalize_french_numbers

FIXTURES = Path(__file__).with_name("fixtures")
# Authored independently of the parser; includes the irregular France forms.
NAMES = (
    "zéro;un;deux;trois;quatre;cinq;six;sept;huit;neuf;dix;onze;douze;treize;"
    "quatorze;quinze;seize;dix-sept;dix-huit;dix-neuf;vingt;vingt et un;vingt-deux;"
    "vingt-trois;vingt-quatre;vingt-cinq;vingt-six;vingt-sept;vingt-huit;vingt-neuf;"
    "trente;trente et un;trente-deux;trente-trois;trente-quatre;trente-cinq;"
    "trente-six;trente-sept;trente-huit;trente-neuf;quarante;quarante et un;"
    "quarante-deux;quarante-trois;quarante-quatre;quarante-cinq;quarante-six;"
    "quarante-sept;quarante-huit;quarante-neuf;cinquante;cinquante et un;"
    "cinquante-deux;cinquante-trois;cinquante-quatre;cinquante-cinq;cinquante-six;"
    "cinquante-sept;cinquante-huit;cinquante-neuf;soixante;soixante et un;"
    "soixante-deux;soixante-trois;soixante-quatre;soixante-cinq;soixante-six;"
    "soixante-sept;soixante-huit;soixante-neuf;soixante-dix;soixante et onze;"
    "soixante-douze;soixante-treize;soixante-quatorze;soixante-quinze;"
    "soixante-seize;soixante-dix-sept;soixante-dix-huit;soixante-dix-neuf;"
    "quatre-vingts;quatre-vingt-un;quatre-vingt-deux;quatre-vingt-trois;"
    "quatre-vingt-quatre;quatre-vingt-cinq;quatre-vingt-six;quatre-vingt-sept;"
    "quatre-vingt-huit;quatre-vingt-neuf;quatre-vingt-dix;quatre-vingt-onze;"
    "quatre-vingt-douze;quatre-vingt-treize;quatre-vingt-quatorze;"
    "quatre-vingt-quinze;quatre-vingt-seize;quatre-vingt-dix-sept;"
    "quatre-vingt-dix-huit;quatre-vingt-dix-neuf"
).split(";")


@pytest.mark.parametrize("number,words", list(enumerate(NAMES)))
def test_group_words_keep_exact_source_span(number, words):
    """All declared 0–99 groups map each digit to the full source phrase."""
    text = "Voilà : " + words + " !"
    normalized, mapping = normalize_french_numbers(text)
    expected = str(number)
    assert normalized == "Voilà : " + expected + " !"
    assert mapping[8 : 8 + len(expected)] == [(8, 8 + len(words))] * len(expected)
    assert len(mapping) == len(normalized)
    assert mapping[-1] == (len(text) - 1, len(text))


@pytest.mark.parametrize(
    "source,expected",
    [
        ("", ""),
        ("aucun chiffre", "aucun chiffre"),
        ("zero SIX douze trente-quatre cinquante-six soixante-dix-huit", "0612345678"),
        ("06 12 trente-quatre 56 soixante-dix-huit", "0612345678"),
        ("+33 six douze trente-quatre cinquante-six soixante-dix-huit", "+33612345678"),
        (
            "zéro\u00a0six, douze, trente‑quatre, cinquante–six, soixante‐dix‐huit",
            "0612345678",
        ),
        ("double zéro, triple SIX, double 2", "0066622"),
        ("quatre vingt et un", "80 et 1"),
        ("quatre-vingt", "80"),
        ("soixante-et-onze", "71"),
        ("six euh douze", "612"),
        ("euh six euh", "euh 6 euh"),
        ("six puis douze", "6 puis 12"),
        ("six' douze", "6' 12"),
        (
            "sixième dixsept nonante septante cent",
            "sixième dixsept nonante septante cent",
        ),
        ("abc06 06abc _six six_", "abc06 06abc _six six_"),
        ("٠٦ １２", "٠٦ １２"),
        ("double douze", "double 12"),
        ("un million", "1 million"),
        ("Le prix est de trente-quatre euros.", "Le prix est de 34 euros."),
        ("Le 16/12/2026, référence ABC0612.", "Le 16/12/2026, référence ABC0612."),
    ],
)
def test_supported_forms_and_unknown_text(source, expected):
    """Unknown words remain barriers; normalization makes no PII decision."""
    normalized, mapping = normalize_french_numbers(source)
    assert normalized == expected
    assert len(mapping) == len(normalized)
    assert all(0 <= start < end <= len(source) for start, end in mapping)


def test_full_phone_span_keeps_surrounding_prose_and_punctuation():
    """Unicode prefixes and apostrophes must not move the original boundaries."""
    prefix = "👋 C’est le "
    answer = "zéro six, douze, trente-quatre, cinquante-six, soixante-dix-huit"
    source = prefix + answer + ". Merci !"
    normalized, mapping = normalize_french_numbers(source)
    start = normalized.index("0612345678")
    assert normalized == prefix + "0612345678. Merci !"
    assert mapping[start][0] == len(prefix)
    assert mapping[start + 9][1] == len(prefix) + len(answer)
    assert source[mapping[start][0] : mapping[start + 9][1]] == answer


def test_written_digits_have_individual_offsets():
    """Mapping a literal substring must not expand to its whole digit run."""
    assert normalize_french_numbers("06 12") == (
        "0612",
        [(0, 1), (1, 2), (3, 4), (4, 5)],
    )


def test_development_positive_annotations_normalize_to_expected_phone():
    """Use only development positives while implementing, never release cases."""
    rows = [
        json.loads(line)
        for line in (FIXTURES / "development.jsonl").read_text().splitlines()
    ]
    positives = [row for row in rows if row["expected_spans"]]
    assert len(positives) == 60
    for row in positives:
        fragments = [row["text"][start:end] for start, end in row["expected_spans"]]
        normalized = "".join(normalize_french_numbers(part)[0] for part in fragments)
        assert normalized == row["canonical_phone"], row["id"]


def test_frozen_files_and_family_split_are_intact():
    """Check release annotations structurally, without evaluating the parser."""
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    families = []
    for name, expected in manifest["files"].items():
        data = (FIXTURES / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected["sha256"]
        rows = [json.loads(line) for line in data.splitlines()]
        assert len(rows) == expected["conversations"]
        assert sum(bool(row["expected_spans"]) for row in rows) == expected["positive"]
        assert len(rows) - expected["positive"] == expected["negative"]
        assert len({row["id"] for row in rows}) == len(rows)
        for row in rows:
            for start, end in row["expected_spans"]:
                assert 0 <= start < end <= len(row["text"])
        families.append(set(row["family"] for row in rows))
    assert not families[0] & families[1]


@pytest.mark.parametrize(
    "source", ["x" * MAX_UTTERANCE_LENGTH, "six" + " " * 9994 + "six"]
)
def test_long_inputs_within_limit(source):
    """Adversarial gaps and nonmatches stay within the documented input bound."""
    normalized, mapping = normalize_french_numbers(source)
    assert normalized in (source, "66")
    assert len(mapping) == len(normalized)


def test_oversized_input_is_rejected_without_echoing_it():
    """Reject excess input with a generic, actionable error."""
    with pytest.raises(
        ValueError, match=r"^Utterance exceeds the 10,000-character limit\.$"
    ):
        normalize_french_numbers("sensitive" + "x" * MAX_UTTERANCE_LENGTH)
