"""A question-then-answer recognizer for call and chat transcripts.

In a transcript, the words that say what a number *is* are often in the
previous speaker's turn:

    AGENT: Okay, what is the number on the card?
    CUSTOMER: four five three nine, one four eight eight, ...

or in an IVR, keyed after a prompt:

    BOT: Please enter your nine digit Social Security number.
    CUSTOMER: 512437788#

Presidio's context enhancement looks for context words around the match in
the same text, so it cannot use the agent's question, and a pattern
recognizer cannot read "four five three nine". This sample recognizer:

1. splits a transcript into speaker turns (``SPEAKER: text``, one per line);
2. when an agent or bot turn asks for an entity (a prompt phrase matches),
   marks the **next customer turn** as that entity;
3. normalizes the customer's answer (spoken digits, "oh", "double",
   "triple", fillers, separators, a trailing keypad ``#``) with an offset map
   back to the original text;
4. joins an answer split across consecutive customer turns;
5. reports the answer with a high score when it passes the entity's check
   (Luhn for a card, the SSA structure rules for an SSN) and a low score when
   it does not. A prompted answer is sensitive whatever its shape, and the
   score lets a threshold decide.

It needs no NLP model. All values in this file are synthetic.

Original sample: crmarr, upstream draft PR #2316, commit
ddfd1893dd78e72f00a1100124d1738dbeab95e9 (MIT). This fork adds an optional
normalizer callback and bounded conversation policy; legacy defaults are retained.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from presidio_analyzer import AnalysisExplanation, EntityRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts

DIGIT_WORDS = {
    "zero": "0",
    "oh": "0",
    "o": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
}
MULTIPLIERS = {"double": 2, "triple": 3}
FILLERS = {"uh", "um", "umm", "er", "erm", "ah", "hmm", "mm"}
SEPARATORS = " -.,"


def normalize_spoken_digits(text: str) -> Tuple[str, List[Tuple[int, int]]]:
    """Normalize spoken and keyed digits, keeping a map back to the original text.

    "four five three nine" becomes "4539", "one oh double five" becomes
    "1055", "512 43 7788#" becomes "512437788". "oh" and "o" are zero only
    next to another digit ("oh, it's one two" keeps its "oh").

    :param text: One turn of a transcript.
    :return: The normalized text, and for each of its characters the
        ``(start, end)`` range of the original text it came from.
    """
    tokens = [
        (m.start(), m.end(), m.group()) for m in re.finditer(r"[A-Za-z]+|.", text, re.S)
    ]
    out: List[Tuple[str, int, int]] = []

    def next_word(i: int) -> Optional[str]:
        for _, _, tok in tokens[i + 1 :]:
            if tok.isspace():
                continue
            return tok.lower()
        return None

    i = 0
    while i < len(tokens):
        start, end, tok = tokens[i]
        word = tok.lower()
        if word in MULTIPLIERS:
            j = i + 1
            while j < len(tokens) and tokens[j][2].isspace():
                j += 1
            if j < len(tokens):
                nxt = tokens[j][2].lower()
                digit = DIGIT_WORDS.get(nxt) or (nxt if nxt.isdigit() else None)
                if digit:
                    out.extend(
                        (digit, start, tokens[j][1]) for _ in range(MULTIPLIERS[word])
                    )
                    i = j + 1
                    continue
        if word in DIGIT_WORDS:
            if word in ("oh", "o"):
                before = "".join(c for c, _, _ in out).rstrip()
                after = next_word(i)
                if not (
                    before[-1:].isdigit()
                    or (after and (after in DIGIT_WORDS or after.isdigit()))
                ):
                    out.extend((c, start + k, start + k + 1) for k, c in enumerate(tok))
                    i += 1
                    continue
            out.append((DIGIT_WORDS[word], start, end))
            i += 1
            continue
        out.extend((c, start + k, start + k + 1) for k, c in enumerate(tok))
        i += 1

    # Drop fillers between digits, separators between digits and a keypad "#".
    text2 = "".join(c for c, _, _ in out)
    keep = [True] * len(out)
    for m in re.finditer(
        r"(?<=[0-9])(?:[ \-.,]|\b(?:%s)\b)+(?=[0-9])" % "|".join(FILLERS), text2, re.I
    ):
        for k in range(m.start(), m.end()):
            keep[k] = False
    for m in re.finditer(r"(?<=[0-9])[#*](?![A-Za-z0-9])", text2):
        keep[m.start()] = False
    kept = [ch for ch, k in zip(out, keep) if k]
    return "".join(c for c, _, _ in kept), [(s, e) for _, s, e in kept]


def luhn_valid(digits: str) -> bool:
    """Check Luhn (mod 10), per ISO/IEC 7812-1.

    :param digits: An ASCII digit string.
    :return: Whether the check digit is consistent.
    """
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def ssn_structure_valid(digits: str) -> bool:
    """Check US SSN structure without verifying identity or issuance.

    :param digits: A nine-digit ASCII string.
    :return: Whether area, group and serial satisfy the structural restrictions.
    """
    area = int(digits[:3])
    return (
        area not in (0, 666)
        and area < 900
        and digits[3:5] != "00"
        and digits[5:] != "0000"
    )


@dataclass(frozen=True)
class PromptedEntity:
    """Describe an entity requested by a prompt and its answer check.

    :param entity: Presidio entity name.
    :param phrases: Trusted developer-supplied prompt regular expressions.
    :param min_digits: Minimum digit count for a complete answer.
    :param max_digits: Maximum digit count for a complete answer.
    :param check: Trusted format/region validation callback.
    """

    entity: str
    phrases: Tuple[str, ...]
    min_digits: int
    max_digits: int
    check: Callable[[str], bool]


DEFAULT_PROMPTS = (
    PromptedEntity(
        "US_SSN",
        (r"social security number", r"\bssn\b"),
        9,
        9,
        lambda d: len(d) == 9 and ssn_structure_valid(d),
    ),
    PromptedEntity(
        "CREDIT_CARD",
        (r"credit card number", r"card number", r"debit card", r"number on the card"),
        13,
        19,
        lambda d: 13 <= len(d) <= 19 and luhn_valid(d),
    ),
)

TURN = re.compile(r"^\s*([A-Za-z][A-Za-z _-]{0,30}):\s?(.*)$")
_NUMBER_RUN = re.compile(r"(?<!\w)\+?[0-9]+(?!\w)")


@dataclass(frozen=True)
class BoundedConversationPolicy:
    """Opt into bounded, same-speaker answers and explicit review markers.

    :param backchannels: Literal asking-speaker acknowledgements allowed between
        answer fragments, ignoring case and terminal punctuation.
    :param review_phrases: Literal words/phrases indicating a correction.
    :param max_answer_turns: Maximum answering turns in one answer.
    :param max_total_turns: Maximum total turns inspected from the first answer.
    :param max_text_length: Maximum transcript length in Python characters.
    :param max_utterance_length: Maximum utterance length in Python characters.
    :param max_transcript_turns: Maximum lines in one transcript.
    """

    backchannels: Tuple[str, ...] = ()
    review_phrases: Tuple[str, ...] = ()
    max_answer_turns: int = 3
    max_total_turns: int = 5
    max_text_length: int = 100_000
    max_utterance_length: int = 10_000
    max_transcript_turns: int = 1_000

    def __post_init__(self) -> None:
        """Reject nonpositive limits without exposing transcript values."""
        limits = (
            self.max_answer_turns,
            self.max_total_turns,
            self.max_text_length,
            self.max_utterance_length,
            self.max_transcript_turns,
        )
        if any(limit <= 0 for limit in limits):
            raise ValueError("Conversation limits must be positive.")


def _backchannel_key(text: str) -> str:
    return text.casefold().replace("’", "'").strip(" \t\r\n.!?…")


class ConversationalPromptRecognizer(EntityRecognizer):
    """Recognize the answer to a question asked in the previous speaker's turn.

    :param prompts: The entities a prompt can ask for, with their phrases
        (regular expressions, matched case-insensitively) and checks.
    :param asking_speakers: Speaker labels whose turns can ask (upper case).
    :param answering_speakers: Speaker labels whose turns answer.
    :param valid_score: The score of an answer that passes its check.
    :param invalid_score: The score of an answer that does not.
    :param max_joined_turns: How many consecutive answering turns can hold one
        answer ("5 1 2" then "4 3" then "7 7 8 8").
    :param supported_language: ISO 639-1 language code.
    :param name: Optional recognizer name.
    :param answer_normalizer: Trusted callback returning normalized text and
        original offsets. Defaults to the original English normalizer.
    :param turn_policy: Optional bounded policy. None preserves the draft's
        original turn handling. Prompt regexes are trusted developer configuration,
        never supplied by transcript users.
    """

    def __init__(
        self,
        prompts: Tuple[PromptedEntity, ...] = DEFAULT_PROMPTS,
        asking_speakers: Tuple[str, ...] = (
            "AGENT",
            "BOT",
            "EMPLOYEE",
            "SYSTEM",
            "IVR",
        ),
        answering_speakers: Tuple[str, ...] = ("CUSTOMER", "CALLER", "USER"),
        valid_score: float = 0.85,
        invalid_score: float = 0.3,
        max_joined_turns: int = 4,
        supported_language: str = "en",
        name: Optional[str] = None,
        answer_normalizer: Callable[
            [str], Tuple[str, List[Tuple[int, int]]]
        ] = normalize_spoken_digits,
        turn_policy: Optional[BoundedConversationPolicy] = None,
    ):
        self.prompts = prompts
        self.asking = {s.upper() for s in asking_speakers}
        self.answering = {s.upper() for s in answering_speakers}
        self.valid_score = valid_score
        self.invalid_score = invalid_score
        self.max_joined_turns = max_joined_turns
        self.answer_normalizer = answer_normalizer
        self.turn_policy = turn_policy
        self._backchannels = (
            {_backchannel_key(value) for value in turn_policy.backchannels}
            if turn_policy
            else set()
        )
        self._review = (
            re.compile(
                r"\b(?:"
                + "|".join(re.escape(p) for p in turn_policy.review_phrases)
                + r")\b",
                re.I,
            )
            if turn_policy and turn_policy.review_phrases
            else None
        )
        self._phrases = [
            (p, re.compile(phrase, re.I)) for p in prompts for phrase in p.phrases
        ]
        super().__init__(
            supported_entities=sorted({p.entity for p in prompts}),
            supported_language=supported_language,
            name=name or "ConversationalPromptRecognizer",
        )

    def load(self) -> None:  # noqa: D102
        pass

    def _asked(self, utterance: str) -> Optional[PromptedEntity]:
        best: Optional[Tuple[int, PromptedEntity]] = None
        for prompted, rx in self._phrases:
            for m in rx.finditer(utterance):
                if best is None or m.end() - m.start() > best[0]:
                    best = (m.end() - m.start(), prompted)
        return best[1] if best else None

    def analyze(
        self, text: str, entities: List[str], nlp_artifacts: NlpArtifacts = None
    ) -> List[RecognizerResult]:
        """Find prompted answers, returning offsets into the original transcript.

        :param text: Transcript with one labelled speaker turn per line.
        :param entities: Entity types to recognize; an empty list allows all.
        :param nlp_artifacts: Unused NLP artifacts; no NLP model is required.
        :return: Recognizer results with original, possibly disjoint spans.
        :raises ValueError: If an opt-in bounded policy's input limit is exceeded.
        """
        if self.turn_policy is not None:
            return self._analyze_bounded(text, entities)
        return self._analyze_legacy(text, entities)

    def _analyze_legacy(self, text: str, entities: List[str]) -> List[RecognizerResult]:
        turns = []  # (speaker, utterance, offset of the utterance in `text`)
        pos = 0
        for line in text.split("\n"):
            m = TURN.match(line)
            if m:
                turns.append((m.group(1).strip().upper(), m.group(2), pos + m.start(2)))
            pos += len(line) + 1

        results: List[RecognizerResult] = []
        armed: Optional[PromptedEntity] = None
        i = 0
        while i < len(turns):
            speaker, utterance, _ = turns[i]
            if speaker in self.asking:
                asked = self._asked(utterance)
                if asked:
                    armed = asked
                i += 1
                continue
            if speaker not in self.answering or armed is None:
                i += 1
                continue
            prompted, armed = armed, None
            if entities and prompted.entity not in entities:
                i += 1
                continue
            # Read the answer: digit runs from this turn, then from the next
            # customer turns while the answer is still too short.
            digits = ""
            spans: Dict[int, Tuple[int, int]] = {}
            j = i
            while j < len(turns) and j - i < self.max_joined_turns:
                sp, utt, offset = turns[j]
                if sp in self.asking and self._asked(utt):
                    break
                if sp not in self.answering:
                    j += 1  # a backchannel from the agent ("mm-hmm") in between
                    continue
                norm, mapping = self.answer_normalizer(utt)
                run = re.search(r"[0-9]+", norm)
                if run is None:
                    break
                digits += run.group()
                spans[j] = (
                    offset + mapping[run.start()][0],
                    offset + mapping[run.end() - 1][1],
                )
                j += 1
                if len(digits) >= prompted.min_digits:
                    break
            if digits:
                valid = prompted.check(digits)
                score = self.valid_score if valid else self.invalid_score
                why = (
                    f"Answer to a prompt for {prompted.entity} in the previous turn; "
                    + ("passes its check." if valid else "does not pass its check.")
                )
                for start, end in spans.values():
                    results.append(
                        RecognizerResult(
                            entity_type=prompted.entity,
                            start=start,
                            end=end,
                            score=score,
                            analysis_explanation=AnalysisExplanation(
                                recognizer=self.name,
                                original_score=score,
                                textual_explanation=why,
                            ),
                            recognition_metadata={
                                RecognizerResult.RECOGNIZER_NAME_KEY: self.name,
                                RecognizerResult.RECOGNIZER_IDENTIFIER_KEY: self.id,
                            },
                        )
                    )
                i = max(j, i + 1)
                continue
            i += 1
        return results

    def _bounded_turns(self, text: str) -> List[Tuple[str, str, int]]:
        policy = self.turn_policy
        if len(text) > policy.max_text_length:
            raise ValueError("Transcript exceeds the character limit.")
        lines = text.splitlines(keepends=True)
        if len(lines) > policy.max_transcript_turns:
            raise ValueError("Transcript exceeds the turn limit.")
        turns = []
        offset = 0
        for segment in lines:
            line = segment.rstrip("\r\n")
            match = TURN.fullmatch(line)
            speaker, utterance, start = (
                (match[1].strip().upper(), match[2], offset + match.start(2))
                if match
                else ("", line, offset)
            )
            if len(utterance) > policy.max_utterance_length:
                raise ValueError("Utterance exceeds the character limit.")
            # Keep unparsed/unknown lines: they are boundaries, never omitted.
            turns.append((speaker, utterance, start))
            offset += len(segment)
        return turns

    def _analyze_bounded(
        self, text: str, entities: List[str]
    ) -> List[RecognizerResult]:
        turns = self._bounded_turns(text)
        results = []
        armed = None
        armed_at = 0
        i = 0
        while i < len(turns):
            if armed is not None and i - armed_at > self.turn_policy.max_total_turns:
                armed = None
            speaker, utterance, _ = turns[i]
            if speaker in self.asking:
                asked = self._asked(utterance)
                if asked:
                    armed = asked
                    armed_at = i
                elif _backchannel_key(utterance) not in self._backchannels:
                    armed = None
                i += 1
                continue
            if speaker not in self.answering:
                armed = None
            if armed is None or speaker not in self.answering:
                i += 1
                continue
            prompted, armed = armed, None
            if entities and prompted.entity not in entities:
                i += 1
                continue
            found, next_turn = self._bounded_answer(turns, i, prompted)
            results.extend(found)
            i = max(i + 1, next_turn)
        return results

    def _bounded_answer(
        self, turns: List[Tuple[str, str, int]], start: int, prompted: PromptedEntity
    ) -> Tuple[List[RecognizerResult], int]:
        policy = self.turn_policy
        customer = turns[start][0]
        digits = ""
        spans = []
        review = False
        valid = False
        answer_turns = 0
        j = start
        while j < len(turns) and j - start < policy.max_total_turns:
            speaker, utterance, offset = turns[j]
            if (
                speaker in self.asking
                and _backchannel_key(utterance) in self._backchannels
            ):
                j += 1
                continue
            if speaker != customer or answer_turns >= policy.max_answer_turns:
                break
            correction = bool(self._review and self._review.search(utterance))
            if valid and not correction:
                break
            review = review or correction
            normalized, mapping = self.answer_normalizer(utterance)
            runs = list(_NUMBER_RUN.finditer(normalized))
            if not runs:
                break
            answer_turns += 1
            review = review or len(runs) != 1
            for run in runs:
                begin = run.start()
                while begin > 0 and normalized[begin - 1] == "+":
                    begin -= 1
                    review = True
                spans.append(
                    (
                        offset + mapping[begin][0],
                        offset + mapping[run.end() - 1][1],
                    )
                )
            digits += runs[0].group()
            digit_count = len(digits.lstrip("+"))
            valid = (
                prompted.min_digits <= digit_count <= prompted.max_digits
                and prompted.check(digits)
            )
            j += 1
            if len(runs) != 1 or digit_count > prompted.max_digits:
                break
        score = self.valid_score if valid and not review else self.invalid_score
        reason = "Bounded same-speaker answer to a prompt; " + (
            "passes the numbering check without a correction marker."
            if valid and not review
            else "incomplete, invalid or ambiguous; human review required."
        )
        results = [
            RecognizerResult(
                entity_type=prompted.entity,
                start=begin,
                end=end,
                score=score,
                analysis_explanation=AnalysisExplanation(
                    recognizer=self.name,
                    original_score=score,
                    textual_explanation=reason,
                ),
                recognition_metadata={
                    RecognizerResult.RECOGNIZER_NAME_KEY: self.name,
                    RecognizerResult.RECOGNIZER_IDENTIFIER_KEY: self.id,
                },
            )
            for begin, end in spans
        ]
        return results, j


if __name__ == "__main__":
    from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
    from presidio_analyzer.nlp_engine import NoOpNlpEngine

    registry = RecognizerRegistry()
    registry.add_recognizer(ConversationalPromptRecognizer())
    analyzer = AnalyzerEngine(
        registry=registry,
        nlp_engine=NoOpNlpEngine(models=[{"lang_code": "en", "model_name": "none"}]),
    )

    # Synthetic values only.
    transcript = "\n".join(
        [
            "EMPLOYEE: If you'd like we can move on to the payment.",
            "CUSTOMER: Yes, I'd like to pay with my credit card.",
            "EMPLOYEE: Okay, what is the number on the card?",
            "CUSTOMER: four five three nine, one four eight eight,",
            "EMPLOYEE: mm-hmm",
            "CUSTOMER: oh three four three, six four six seven.",
            "BOT: Please enter your nine digit Social Security number.",
            "CUSTOMER: 512437788#",
        ]
    )
    for r in analyzer.analyze(transcript, language="en"):
        print(r.entity_type, round(r.score, 2), r.start, r.end)
