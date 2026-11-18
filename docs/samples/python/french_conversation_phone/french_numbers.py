"""Normalize the declared French phone-number grammar without detecting PII.

The return format is compatible with the English normalizer in the draft
conversation sample, upstream PR #2316 by crmarr. This module is independent
of that unmerged draft and does not alter Presidio's shared normalizers.
"""

import re
from typing import Dict, List, Tuple

MAX_UTTERANCE_LENGTH = 10_000
_DIGITS = (
    "zéro",
    "un",
    "deux",
    "trois",
    "quatre",
    "cinq",
    "six",
    "sept",
    "huit",
    "neuf",
)
_TEENS = ("dix", "onze", "douze", "treize", "quatorze", "quinze", "seize")
_TENS = ("", "", "vingt", "trente", "quarante", "cinquante", "soixante")
_WORD_SEPARATOR = r"[\s\-‐‑–]+"
_GAP = re.compile(r"(?:[\s,\.\-‐‑–]|euh)+", re.IGNORECASE)


def _number_words(number: int) -> str:
    if number < 10:
        return _DIGITS[number]
    if number < 17:
        return _TEENS[number - 10]
    if number < 20:
        return "dix " + _DIGITS[number - 10]
    if number < 70:
        tens, unit = divmod(number, 10)
        if unit == 0:
            return _TENS[tens]
        connector = " et " if unit == 1 else " "
        return _TENS[tens] + connector + _DIGITS[unit]
    if number < 80:
        return "soixante " + ("et onze" if number == 71 else _number_words(number - 60))
    if number == 80:
        return "quatre vingts"
    return "quatre vingt " + _number_words(number - 80)


def _forms() -> Dict[str, str]:
    forms = {_number_words(n): str(n) for n in range(100)}
    forms.update({"zero": "0", "quatre vingt": "80"})
    forms.update({str(n): str(n) for n in range(10)})
    for word, digit in list(forms.items()):
        if len(digit) == 1:
            forms["double " + word] = digit * 2
            forms["triple " + word] = digit * 3
    return forms


_FORMS = _forms()
_NUMBER = re.compile(
    r"(?<!\w)(?:[0-9]+|"
    + "|".join(
        _WORD_SEPARATOR.join(re.escape(word) for word in form.split())
        for form in sorted(_FORMS, key=len, reverse=True)
    )
    + r")(?!\w)",
    re.IGNORECASE,
)
_COLLAPSE_SEPARATORS = re.compile(_WORD_SEPARATOR)


def normalize_french_numbers(text: str) -> Tuple[str, List[Tuple[int, int]]]:
    """Normalize French digit/group words and retain original character offsets.

    Non-number text is preserved. This utility does not determine whether a
    number is sensitive, complete, valid, or appropriate in its context.

    :param text: One utterance, at most 10,000 Python characters.
    :return: Normalized text and one original ``(start, end)`` range per output
        character. Offsets are end-exclusive; a group word can emit two digits
        with the same source range.
    :raises ValueError: If the utterance exceeds the input limit. The message
        does not contain the supplied text.
    """
    if len(text) > MAX_UTTERANCE_LENGTH:
        raise ValueError("Utterance exceeds the 10,000-character limit.")

    output: List[str] = []
    mapping: List[Tuple[int, int]] = []
    previous_end = 0
    has_number = False
    for match in _NUMBER.finditer(text):
        source = match.group()
        literal = source.isascii() and source.isdigit()
        key = _COLLAPSE_SEPARATORS.sub(" ", source.lower())
        digits = source if literal else _FORMS.get(key)
        # Python's Unicode case-insensitive regex also matches characters such
        # as dotted I. Preserve unsupported forms rather than guessing or
        # raising a KeyError containing input text.
        is_number = digits is not None
        gap = text[previous_end : match.start()]
        if not (has_number and is_number and _GAP.fullmatch(gap)):
            output.append(gap)
            mapping.extend((i, i + 1) for i in range(previous_end, match.start()))

        if literal or not is_number:
            output.append(source)
            mapping.extend((i, i + 1) for i in range(match.start(), match.end()))
        else:
            output.append(digits)
            mapping.extend((match.start(), match.end()) for _ in digits)
        previous_end = match.end()
        has_number = is_number

    output.append(text[previous_end:])
    mapping.extend((i, i + 1) for i in range(previous_end, len(text)))
    return "".join(output), mapping
