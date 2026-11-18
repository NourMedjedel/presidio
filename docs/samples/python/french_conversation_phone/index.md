# French spoken-phone normalization (experimental)

A customer can answer a phone prompt with “zéro six, douze, trente-quatre…”
instead of written digits. This sample prepares French number groups for
recognition while mapping every output character back to the original words.
It runs locally on CPU with no LLM, API account or NLP-model download.

**Implemented:** normalization and exact offsets, a configured French baseline,
and a frozen synthetic conversation corpus. Conversation recognition and
Analyzer-to-Anonymizer redaction are still planned. This utility alone does
not detect or anonymize PII. No release accuracy is claimed.

## Run from a checkout

Use Python 3.11–3.14 and uv. The recorded run used Python 3.12.14. From the
repository root:

```bash
cd presidio-analyzer
uv sync --locked --group dev
uv run --locked python ../docs/samples/python/french_conversation_phone/baseline.py
uv run --locked pytest ../docs/samples/python/french_conversation_phone -q
```

The first command installs the analyzer's locked dependencies and test tools;
it needs network access once. Runtime does not contact a model provider.
The core baseline CLI reports case IDs, spans and scores, without transcript
values. All checked-in examples are synthetic.

To use the standalone utility, place its directory on your Python import path:

```python
from french_numbers import normalize_french_numbers

text = "C’est le zéro six, douze, trente-quatre, cinquante-six, soixante-dix-huit."
normalized, mapping = normalize_french_numbers(text)
start = normalized.index("0612345678")
original_start = mapping[start][0]
original_end = mapping[start + 9][1]
# original_start/original_end select the spoken answer, excluding the period.
```

The utility has no dependency on Presidio. It keeps unknown words, surrounding
prose and offsets intact. Input is bounded to 10,000 characters. See the
[declared grammar, limitations and evaluation policy](scope.md).

## What already works upstream

Baseline pinned to upstream `fd78e974fbf9e15dad1f90de4fc125db39ef4200`,
analyzer 2.2.366, phonenumbers 9.0.41 and spaCy 3.8.16. The analyzer lockfile
hash and original spans/scores are in [the recorded probe](baseline-results.json).
The registry, recognizer and analyzer all use `fr`, region `FR`, and threshold
`0.35`. `NoOpNlpEngine` provides no NER, tokens or lemmas, so configured French
context words do not receive implicit textual-context boosts. This isolates
the phone and conversation recognizers; it is not a comparison with French NER.

| Eight synthetic probe cases | Core phone recognizer | Core + configured draft #2316 |
| --- | --- | --- |
| Written national number | Exact span | Exact span |
| Written `+33` number | Exact span | Extra overlapping span omits `+` |
| French digit words | Missed | Missed |
| French 0–99 groups | Missed | Missed |
| Spoken groups split across turns | Missed | Missed |
| Quantity, price, missing-prompt negatives | No matches | No matches |

These eight cases diagnose a gap. They are not a representative benchmark or
a performance estimate. The frozen 220-conversation corpus is for the later
recognizer evaluation; its release split has not been evaluated or used for
tuning the normalizer.

## Existing work and reuse

Reviewed on 18 November 2026, before implementation:

- [#2315](https://github.com/data-privacy-stack/presidio/issues/2315) already
  requests conversation-aware recognition.
- [Draft #2316](https://github.com/data-privacy-stack/presidio/pull/2316), by
  **crmarr**, implements an English conversation sample. Its language is
  configurable, but its spoken-number vocabulary is English. The comparison
  pins head `ddfd1893dd78e72f00a1100124d1738dbeab95e9`. The French utility
  deliberately uses its `(normalized_text, offset_map)` contract. Reuse or
  rebase that sample when adding French recognition; do not publish a competing
  generic conversation engine or imply that the draft is merged.
- The old French-region typo
  [#2008](https://github.com/data-privacy-stack/presidio/issues/2008) is already
  fixed. `PhoneRecognizer` already supports France. There is no new core
  French-phone recognizer or default-registry change here.
- French NIR [#2314](https://github.com/data-privacy-stack/presidio/pull/2314)
  and SIREN/SIRET [#2321](https://github.com/data-privacy-stack/presidio/pull/2321)
  are open work outside this scope. Do not duplicate them.
- The text-normalization interface
  [#2397](https://github.com/data-privacy-stack/presidio/pull/2397) is merged;
  Unicode-digit [#2480](https://github.com/data-privacy-stack/presidio/pull/2480)
  and Arabic [#2422](https://github.com/data-privacy-stack/presidio/pull/2422)
  remain open. Unicode-digit conversion and Arabic are deferred.

### Reproduce the configured draft comparison

Fetch the reviewed sample **separately**, retaining its upstream provenance:

```bash
curl --fail --location https://raw.githubusercontent.com/data-privacy-stack/presidio/ddfd1893dd78e72f00a1100124d1738dbeab95e9/docs/samples/python/conversational_prompt_recognizer/conversational_prompt_recognizer.py --output /tmp/conversational_prompt_recognizer.py
shasum -a 256 /tmp/conversational_prompt_recognizer.py
```

Expected SHA-256:
`261cf67d036317f9bfde54b8978a95b504746e6563a4a5b9f26d2448a1310103`.
From `presidio-analyzer`, run:

```bash
PYTHONPATH=/tmp:../docs/samples/python/french_conversation_phone uv run --locked python - <<'PY'
import json
from baseline import create_analyzer, measure, valid_french_phone
from conversational_prompt_recognizer import (
    ConversationalPromptRecognizer,
    PromptedEntity,
)

draft = ConversationalPromptRecognizer(
    supported_language="fr",
    prompts=(
        PromptedEntity(
            "PHONE_NUMBER",
            (r"numéro de téléphone", r"numéro de portable"),
            10,
            10,
            valid_french_phone,
        ),
    ),
    asking_speakers=("AGENT", "BOT"),
    answering_speakers=("CLIENT", "CUSTOMER"),
)
print(json.dumps(measure(create_analyzer(draft)), indent=2))
PY
```

No upstream code is vendored or modified by this first step. When that draft
changes, recheck its implementation and tests before choosing an integration.

## Next gate

Add a French-normalizer callback to the existing conversation sample, then
implement the bounded role/prompt policy in [the frozen scope](scope.md).
Verify disjoint original spans and public Analyzer-to-Anonymizer redaction.
Review incomplete/corrected answers rather than inventing missing digits.
Keep changed English behavior explicit, add compatibility tests and meet the
frozen evaluation gates before releasing or recording a redaction demo.
