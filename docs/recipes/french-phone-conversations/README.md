# French phone answers in customer-service conversations

**Domain:** French customer-service call/chat transcripts.  
**Data type:** Text with explicit speaker labels; no audio or speech recognition.  
**Goal:** Recognize France phone answers spoken as words or split across turns,
preserving original positions and unrelated agent messages.

This recipe follows **data synthesis → configuration → evaluation**. It runs
locally on CPU without an LLM, paid account, GPU or NLP-model download.

## Quick start

Use Python 3.11–3.14 and uv, from a checkout of
[this fork](https://github.com/NourMedjedel/presidio). Choose unused output paths:

```bash
cd presidio-analyzer
uv sync --locked --group dev
export PYTHONPATH=../docs/samples/python/conversational_prompt_recognizer:../docs/samples/python/french_conversation_phone

uv run --locked python ../docs/recipes/french-phone-conversations/generate_data.py \
  /tmp/french-phone-recipe-data

uv run --locked --with ../presidio-anonymizer --with cryptography==50.0.2 \
  python ../docs/recipes/french-phone-conversations/configure.py

uv run --locked --with ../presidio-anonymizer --with cryptography==50.0.2 \
  python ../docs/recipes/french-phone-conversations/evaluate_recipe.py \
  --data /tmp/french-phone-recipe-data --output /tmp/french-phone-recipe-results.json
```

Installation needs network access once. Runtime does not contact a model provider.
These commands passed in a fresh clone and virtual environment (download cache
reused). [CI](https://github.com/NourMedjedel/presidio/actions/runs/44237271364)
passes 248 sample/recipe tests on Python 3.11–3.14; recipe-code coverage is 97%.
The example prints original-position detections and this redacted output:

```text
AGENT: Quel est votre numéro de téléphone ?
CLIENT: <PHONE_NUMBER>
AGENT: Oui.
CLIENT: <PHONE_NUMBER>.
```

## Approach

- [Generate data](generate_data.py): authored number spellings and marked-up
  annotations produce 220 synthetic conversations. No detector labels its own
  test data. All three output files must match the original frozen v1 hashes.
- [Configure Presidio](configure.py): compare a correctly configured `fr`/`FR`
  core phone recognizer with the additive French conversation recognizer, both
  at threshold `0.35` with NoOpNlpEngine.
- [Evaluate](evaluate_recipe.py): count exact entity/start/end matches, retaining
  every failed case's missing/surplus spans. Identical duplicates count once;
  shifted or merged spans earn no partial credit. The full sample's review gate
  withholds incomplete/corrected answers before combined-result de-duplication.

Supported grammar, role boundaries and review limitations are documented in the
[implementation guide](../../samples/python/french_conversation_phone/index.md)
and [scope](../../samples/python/french_conversation_phone/scope.md).

## Results

The following table is derived from the existing
[frozen v1 evaluation](../../samples/python/french_conversation_phone/reports/README.md),
without modifying or rerunning that recorded result:

[Machine-readable derived metrics](results-v1.json) retain the source report's checksum.

| Configuration | Precision | Recall | Exact-span F₂ | Mean recognition latency |
| --- | ---: | ---: | ---: | ---: |
| Configured core | 1.000 | 0.167 | 0.200 | 0.021 ms/sample |
| Core + French sample | 1.000 | 1.000 | 1.000 | 0.050 ms/sample |

Micro F₂ is `5TP / (5TP + 4FN + FP)`. The baseline finds 20 spans and misses 100;
the extension finds all 120 with no additional spans. These are exact-span scores,
not interchangeable with token-level or partial-overlap evaluations.

The means use saved **first-pass** per-case recognition times on Apple M3,
Python 3.12.14. They exclude imports, engine construction and anonymization,
include the first request, and differ from the separate warm p95 benchmark.
Fresh runs measure their own means; these are short synthetic texts, not an SLA.

To reproduce this table without new predictions, use the same uv command with
`evaluate_recipe.py --saved-report` pointing to
`../docs/samples/python/french_conversation_phone/reports/evaluation-v1.json`.
Existing results are never overwritten.

### Key findings and limits

- The core recognizer already handles written French phones. The added value is
  declared spoken-number forms and bounded prompted answers across turns.
- Data are project-authored and template-generated: 100 positives, 120 negatives,
  only 20 mobile values, and known overlap with earlier probes. This is regression
  evidence, not independent or production validation. Original split labels and
  historical manifest metadata are retained for byte-for-byte reproduction.
- Unsupported paraphrases, unmarked corrections, other countries and speech-to-text
  errors can be missed. Negative annotations concern the prompted phone-answer
  task, not every possible personal identifier. This does not guarantee anonymity.
- Scores `0.7`/`0.2` are policy values, not calibrated probabilities. Review behavior
  has named unit tests; this corpus has no separately annotated review examples.

## Dependency and upstream status

This fork supplies the helpers in `docs/samples/python/french_conversation_phone/`
and `docs/samples/python/conversational_prompt_recognizer/`. A stock package
installation alone does not supply this recipe's custom modules. The scripts
reuse public helper functions rather than duplicating the recognizer.

The conversation engine derives from **crmarr**'s unmerged
[draft #2316](https://github.com/data-privacy-stack/presidio/pull/2316), pinned at
`ddfd1893dd78e72f00a1100124d1738dbeab95e9`, with original authorship and MIT
attribution retained. Its English defaults remain unchanged. Helper integration
must be agreed before an upstream recipe PR; this fork is not upstream endorsement.

**Author:** Nour Medjedel · **Date:** 2026-11-18 · **License:** [MIT](../../../LICENSE)
