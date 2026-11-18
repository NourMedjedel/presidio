"""Opt-in France phone answers using the attributed conversation sample."""

import re
from typing import Optional

import phonenumbers
from conversational_prompt_recognizer import (
    BoundedConversationPolicy,
    ConversationalPromptRecognizer,
    PromptedEntity,
)
from french_numbers import normalize_french_numbers

_PHONE_FORM = re.compile(r"(?:0[0-9]{9}|\+33[0-9]{9})")
_PHONE_WORDS = r"num[ée]ro\s+de\s+(?:t[ée]l[ée]phone|portable|mobile)\b"
_PROMPTS = (
    r"^\s*quel\s+est\s+votre\s+" + _PHONE_WORDS,
    r"^\s*pouvez[- ]vous\s+(?:me\s+)?(?:donner|indiquer)\s+votre\s+" + _PHONE_WORDS,
    r"^\s*(?:indiquez|donnez|saisissez|dictez)(?:[- ]moi)?\s+votre\s+" + _PHONE_WORDS,
)


def valid_french_phone_answer(value: str) -> bool:
    """Validate explicit national/+33 forms against France's numbering plan.

    Uses phonenumbers metadata, as Presidio's core phone recognizer does.
    This is not a checksum, ownership check or reachability check.

    :param value: Normalized phone answer, retaining an explicit leading plus.
    :return: Whether the form and region validation both pass.
    """
    if not _PHONE_FORM.fullmatch(value):
        return False
    return phonenumbers.is_valid_number_for_region(
        phonenumbers.parse(value, "FR"), "FR"
    )


class FrenchPhoneConversationRecognizer(ConversationalPromptRecognizer):
    """Recognize France phone answers under the sample's frozen bounded policy.

    Custom Python sample, registered explicitly; not a core/YAML recognizer.
    Supported language is ``fr``. Scores 0.7/0.2 are policy values, not calibrated
    probabilities. Review candidates must be handled separately by callers.

    :param name: Optional recognizer name for explanations and registry metadata.
    """

    def __init__(self, name: Optional[str] = None):
        super().__init__(
            prompts=(
                PromptedEntity(
                    "PHONE_NUMBER", _PROMPTS, 10, 11, valid_french_phone_answer
                ),
            ),
            asking_speakers=("AGENT", "BOT", "CONSEILLER"),
            answering_speakers=("CLIENT", "UTILISATEUR"),
            supported_language="fr",
            name=name or "FrenchPhoneConversationRecognizer",
            answer_normalizer=normalize_french_numbers,
            valid_score=0.7,
            invalid_score=0.2,
            turn_policy=BoundedConversationPolicy(
                backchannels=("oui", "d'accord", "je vous écoute"),
                review_phrases=(
                    "non",
                    "pardon",
                    "corrige",
                    "correction",
                    "rectifie",
                    "trompé",
                    "annule",
                    "annulez",
                    "annuler",
                    "annulation",
                    "oubliez",
                ),
            ),
        )
