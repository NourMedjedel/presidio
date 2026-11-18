# French sample: regression and resource results

Candidate source: [`4ea7518`](https://github.com/NourMedjedel/presidio/commit/4ea7518b0617e7dfd6bcb983657b67e641d20a35).
[Source/data pins](../candidate-v1.json) · [Complete results and every failure](evaluation-v1.json) · [Compatibility evidence](compatibility-v1.json) · [CI run](https://github.com/NourMedjedel/presidio/actions/runs/44229522396).

The full **220-conversation** corpus contains 100 positives, 120 negatives and
120 annotated phone spans. It is project-authored/template-generated synthetic
regression data. Known families and some exact cases overlap earlier probes;
these results are **not independent validation or production accuracy**.
Only 20 generated mobile-phone values are reused across the positive families;
this corpus does not establish coverage of all France phone formats.

## Exact original-text spans

| Configuration | TP | FP | FN | Span recall | Exact conversations | Exact redaction output |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Configured core phone recognizer | 20 | 0 | 100 | 16.7% | 140/220 | 140/220 |
| Core + French conversation sample | 120 | 0 | 0 | 100.0% | 220/220 | 220/220 |

Both configurations use `fr`, region `FR`, threshold `0.35` and NoOpNlpEngine.
No NER model, LLM judge, hosted API or GPU is used. Identical triples are
deduplicated; shifted/merged spans receive no partial credit. Output success is
checked through the public anonymizer, preserving unrelated text and agent turns.
Precision is 100% overall for both: the baseline makes only 20 predictions.

The labelled release subset has 80 conversations and 60 expected spans. The
baseline misses all 60 spans (precision undefined: no predictions); the French
sample matches all 60, with all 80 outputs exact. The frozen 95% precision/recall
targets pass on that subset. This does not make it an independent holdout.

Baseline failures remain in the JSON: 80 conversations, 100 missing spans.
The candidate has 0 failures on this corpus. No failed cases were deleted or
changed, and no threshold was retuned after this run. Review/cancellation cases
are covered by named unit tests, not annotated review examples in this corpus.
Negative annotations test the prompted customer-answer task, not all possible PII.

## Compatibility

[GitHub Actions](https://github.com/NourMedjedel/presidio/actions/runs/44229522396) passed on **Python 3.11, 3.12, 3.13 and 3.14**.
Each job runs 242 English/French/evaluator sample tests, two model-free upstream
phone checks and 32 upstream anonymizer-engine/replace/redact tests. Local initial
implementation checks also passed on all four versions; their smaller 226-test
count predates the evaluator and is recorded separately.

25 model-dependent core phone tests were deselected. The complete optional
NLP/GPU/cloud and other-component suites were not run. Canonical package locks,
versions and core defaults are unchanged. This stage's evaluator has 96% changed
executable-line coverage; combined sample-module coverage is 94% on Python 3.12.

## Resource measurements

One local serial run on **Apple M3, 8 logical CPUs**, macOS-26.5.2-arm64-arm-64bit,
Python 3.12.14. Five warm timing passes per configuration
(1100 observations), nearest-rank p95. Quality outcomes are recorded separately
and are never replaced by a later timing pass. Engine construction/imports are
excluded from the warm figures. These are short synthetic texts, not a server SLA.

| Warm recognition | Median | p95 |
| --- | ---: | ---: |
| Core | 0.009 ms | 0.064 ms |
| Core + French sample | 0.019 ms | 0.114 ms |

The actual candidate workflow, including per-request construction and public
anonymizer output, measured median 0.085 ms / p95
0.221 ms across 220 calls. It is reported separately from reused-engine timings.
Peak process RSS was **106.2 MiB**, including Python/imports, both analyzers,
fixtures and stress tests; it is not incremental model memory or a memory limit.

| Bounded workload | Characters | Turns | Outcome | p95 (5 calls) |
| --- | ---: | ---: | --- | ---: |
| repeated_fillers | 8,112 | 2 | returned | 4.196 ms |
| near_text_limit | 90,081 | 18 | returned | 2.084 ms |
| maximum_turns | 20,000 | 1,000 | returned | 2.285 ms |
| over_text_limit | 100,001 | 1 | rejected | 0.013 ms |

All four expected resource outcomes passed. The oversized transcript is rejected
before core detection, with a generic error. The report contains IDs, scores and
positions, not input values or transcript output.

## Reproduce

From the checkout root, use a new output path; existing candidates/reports are
never overwritten:

```bash
cd presidio-analyzer
uv sync --locked --group dev
export PYTHONPATH=../docs/samples/python/conversational_prompt_recognizer:../docs/samples/python/french_conversation_phone
uv run --locked --with ../presidio-anonymizer --with cryptography==50.0.2 \
  python ../docs/samples/python/french_conversation_phone/evaluate.py \
  --candidate ../docs/samples/python/french_conversation_phone/candidate-v1.json \
  --output /tmp/french-evaluation-reproduction.json
```

Source/data hashes are checked before predictions. Timing and memory can vary;
compare quality counts and pins, not byte-identical report timestamps. A source
change requires committing it, freezing a **new** candidate with `--freeze`, and
retaining the earlier report. Independent or real-transcript validation remains
future work. No French release tag is created by the evaluator.
