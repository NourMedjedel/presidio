# French phone answers in conversations (experimental)

A customer can answer a phone prompt with “zéro six, douze, trente-quatre…”
instead of written digits, sometimes across several turns. This opt-in sample
recognizes and replaces those answers using exact spans in the original text.
It runs locally on CPU with no LLM, API account or NLP-model download.

**Implemented:** French normalization, bounded same-speaker recognition, disjoint
spans, a separate review gate and public Analyzer-to-Anonymizer redaction. This is
a phone-only experiment, not a guarantee that text is anonymous. The full
synthetic corpus and Python 3.11–3.14 matrix pass their declared checks. See the
[measured results and limitations](reports/README.md): this is narrow regression
evidence, not independent or production validation.

## Run from a checkout

Use Python 3.11–3.14 and uv. The recorded run used Python 3.12.14. From the
repository root:

```bash
cd presidio-analyzer
uv sync --locked --group dev
export PYTHONPATH=../docs/samples/python/conversational_prompt_recognizer:../docs/samples/python/french_conversation_phone
uv run --locked python ../docs/samples/python/french_conversation_phone/baseline.py
uv run --locked --with ../presidio-anonymizer --with cryptography==50.0.2 \
  python ../docs/samples/python/french_conversation_phone/redact.py
uv run --locked --with ../presidio-anonymizer --with cryptography==50.0.2 \
  python ../docs/samples/python/french_conversation_phone/redact.py --scenario correction
uv run --locked --with ../presidio-anonymizer --with cryptography==50.0.2 \
  pytest ../docs/samples/python/conversational_prompt_recognizer \
  ../docs/samples/python/french_conversation_phone -q
```

The first command installs the analyzer's locked dependencies and test tools;
it needs network access once. `--with` builds this checkout's anonymizer in a
temporary uv environment; its cryptography version matches the anonymizer lock.
No analyzer/anonymizer dependency files are modified. Runtime does not contact
a model provider.
The core baseline CLI reports case IDs, spans and scores, without transcript
values. All checked-in examples are synthetic.

The split-answer demo prints:

```text
AGENT: Quel est votre numéro de téléphone ?
CLIENT: <PHONE_NUMBER>
AGENT: Oui.
CLIENT: <PHONE_NUMBER>.
```

The correction demo withholds transcript output and prints only review positions.
Review candidates are checked **before** core-result de-duplication, so a generic
phone score cannot hide an answer requiring human review. The sample replaces
phone values without maintaining a reversible mapping.

Prompts must start with `Quel est votre numéro de…`, `Pouvez-vous [me]
donner/indiquer votre numéro de…`, or `Indiquez/Donnez[-moi]/Saisissez/Dictez
votre numéro de…`, followed by `téléphone`, `portable` or `mobile`. Accented and
unaccented forms are supported. Arbitrary paraphrases are not inferred.
Corrected or withdrawn answers use a finite list of review markers (including
`non`, `pardon`, `corrige`, `annulez`, `oubliez`) or multiple numeric runs.
Unmarked corrections and unsupported prompts can be missed. Read the
[role, boundary, input-limit and scoring policy](scope.md) before using real data.

This is a custom Python sample registered with `registry.add_recognizer(...)`.
It is not a new core predefined recognizer or a YAML-loadable sample class.
The configuration test loads the core French registry through
`RecognizerRegistryProvider`, then explicitly registers the custom recognizer.

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
recognizer evaluation. The full corpus has now been run without changing its
hashes or threshold: [complete report](reports/evaluation-v1.json). Its families
and some exact cases overlap baseline/unit probes. Treat it as frozen
project-authored regression evaluation, not independent or unseen-family validation.

The extended French recognizer matches all eight diagnostic cases exactly;
[results and pinned implementation hashes](conversation-probe-results.json).
The combined sample suite passes **242 tests**, including the
original English tests, direct/registry construction, a French YAML-loaded core
registry with the custom sample added, and real anonymizer output. Coverage is
100% for French normalization and its configured recognizer, 94% across the
sample modules, and 96% of this stage's changed executable lines. The
[CI matrix](https://github.com/NourMedjedel/presidio/actions/runs/44229522396)
passes on Python 3.11–3.14, including two model-free core phone checks and 32
anonymizer checks per job. Full optional NLP/GPU/cloud suites are not run.

With the import path configured above, reproduce the current diagnostic check:

```bash
uv run --locked python - <<'PY'
import json
from baseline import create_analyzer, measure
from french_phone_recognizer import FrenchPhoneConversationRecognizer
print(json.dumps(measure(create_analyzer(FrenchPhoneConversationRecognizer())), indent=2))
PY
```

## Existing work and reuse

Reviewed on 18 November 2026, before implementation:

- [#2315](https://github.com/data-privacy-stack/presidio/issues/2315) already
  requests conversation-aware recognition.
- [Draft #2316](https://github.com/data-privacy-stack/presidio/pull/2316), by
  **crmarr**, implements an English conversation sample. Its language is
  configurable, but its spoken-number vocabulary is English. The comparison
  pins head `ddfd1893dd78e72f00a1100124d1738dbeab95e9`. The French utility
  uses its `(normalized_text, offset_map)` contract. The draft commit is now
  cherry-picked with original authorship and an origin trailer. The French
  feature extends that engine with a callback and opt-in bounded policy;
  the upstream draft is still unmerged. Original English tests are retained.
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

This comparison deliberately downloads the **pristine** draft, not the extended
local copy. When upstream changes, recheck it before rebasing or submitting work.
The local English engine keeps its original defaults and results; its synthetic
CLI now prints entity types, scores and positions instead of values.

## Next gate

The [frozen candidate](candidate-v1.json),
[full regression/resource report](reports/README.md) and CI evidence are available.
Next: a short README recording and release review. Independent/real-transcript
validation remains future work; passing synthetic cases is not a guarantee of
anonymity. Arabic remains a later workstream.
