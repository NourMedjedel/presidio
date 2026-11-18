# French phone conversation scope (v1)

This is an experimental, opt-in sample under development. It handles text,
not audio. France (`FR`) phone numbers and language `fr` are the target.
It does not establish that a number belongs to someone or is reachable.

## Number grammar

- ASCII digits, single French digit words, or standard France French groups
  from 0 to 99. Preserve leading zeros. Mixed digits and words are allowed.
- `zéro` and `zero`, upper/lower case, `double` or `triple` followed by a
  **single digit**. No inference of missing digits or ambiguous homophones.
- Standard `soixante-dix`, `soixante et onze`, `quatre-vingts`,
  `quatre-vingt-un` and `quatre-vingt-dix-neuf`; spaces or hyphens between
  their words. `quatre-vingt` alone is accepted as a common transcription.
- Spaces (including non-breaking spaces), hyphens (`-`, `‐`, `‑`, `–`), commas
  and periods may separate groups. `euh` is ignored only between numbers.
  Apostrophes in surrounding prose remain unchanged, not digit separators.
- National ten-digit form including the leading `0`, or explicit `+33`
  followed by nine digits. Do not silently add a national zero, remove a
  duplicated `(0)`, interpret `0033`, or translate a foreign region.
- Unsupported text remains text, separating candidate runs. The normalizer
  neither detects PII nor validates a phone number. For example, a price is
  also normalizable; context and phone validation belong to the recognizer.
- Maximum normalization input: 10,000 characters per utterance. Oversized
  input raises an error with no input values. No shared conversation state.

Excluded: `septante`, `huitante`, `nonante`, hundreds, fractional numbers,
Unicode decimal-digit conversion, decomposed accent normalization, ASR
homophone repair and automatic correction of malformed number words.

## Conversation policy

Each line is one explicitly labelled turn. Asking roles are `AGENT`, `BOT`,
or `CONSEILLER`; answering roles are `CLIENT` or `UTILISATEUR`. Labels must
identify one person per role in a transcript. Changing the answering label
ends an answer; this sample will not infer identity from free-form diarization.

A phone prompt applies to the next answer only. Join at most three answer
turns within five total turns. An intervening asking turn must be exactly a
declared backchannel (`oui`, `d'accord`, `je vous écoute`, ignoring terminal
punctuation); another question, unknown speaker or unparseable line resets
the pending answer. Never join different transcripts or customer identities.
Re-prompt explicitly to retry. Limit a transcript to 100,000 characters and
1,000 turns; reject oversized input without logging its content.

Only a complete answer passing `phonenumbers` France validation is a validated
candidate (score `0.7`, **not** a calibrated probability). Incomplete,
invalid, ambiguous or corrected answers must be surfaced as review candidates
(score `0.2`) rather than completed or presented as validated. A
threshold of `0.35` excludes review candidates from automatic redaction, so
applications must handle review separately. This is not a privacy guarantee.
Corrections never overwrite prior sensitive spans: both supplied versions
require review within the bounded answer. These policies are implemented by the
opt-in conversation recognizer; the number normalizer alone makes no PII decision.

Implementation clarifications (18 November 2026): the pending prompt also expires
after five intervening turns; correction detection uses documented literal
markers and multiple numeric runs, not semantic inference. The redaction helper
withholds output when any review candidate is present, before combined-result
de-duplication. Fixtures, split hashes, threshold and evaluation targets are
unchanged. Unsupported paraphrases/unmarked corrections can be missed.

## Frozen evaluation rubric

`fixtures/manifest.json` pins development and release JSONL files by SHA-256.
They contain 100 positive and 120 negative synthetic conversations. They were
authored for this project before the normalizer, without using its outputs.
They are template-generated, not independent review or production validation.
Generated combinations may coincide with real phone numbers: never contact them.

Annotations use Python character offsets into the original text, end exclusive,
excluding speaker labels, surrounding prose and trailing punctuation. For a
split answer, every contributing turn has a separate span. Do not redact the
intervening agent turn. Each positive also specifies the expected canonical
phone for checking normalization independently of detection.

Development families: written digits, spoken digits, spoken groups, quantities,
prices, dates and order references. Release families: split answers,
international forms, changed topic and unknown speakers. This is a holdout by
scenario family; the same synthetic phone values recur across splits. It does
not test independence of vocabulary or phone values. Use development cases
while implementing; do not tune against release outcomes. Changes to fixtures
require a new version and disclosure of previous results.

Evaluation provenance clarification: baseline and feature unit probes cover the
known release families, and some cases overlap the release file. The full release
file has now been evaluated without changing its hashes or threshold. It is a
**frozen project-authored regression set**, not an unseen-family or independent
holdout. Keep this overlap visible in the report; independent validation requires
new external cases.

At the fixed threshold `0.35`, count exact `(entity, start, end)` matches as true
positives. A shifted, merged, missing or additional span is an error; partial
overlap gives no credit. De-duplicate identical predictions. Report precision,
recall, false positives by family and the proportion of conversations whose
entire span set is correct (including negative conversations). Report both
missing and surplus spans, not only an aggregate percentage.

Release gates: at least 95% exact-span precision and recall on the frozen release
set, plus all named critical regressions: missing prompt, consumed prompt,
unrelated question, unknown speaker, customer change, unparseable boundary,
incomplete/invalid number, correction, disjoint offsets, request isolation,
entity filtering and input bounds. These targets are fixed before implementation
and are not achieved results. Validate redaction through public Analyzer and
Anonymizer APIs. Compare configurations at the same threshold and NLP settings.
Keep baseline false positives visible, including existing generic-phone matches.

No real transcripts, audio or personal records are included. A future independent
review should be recorded with its actual authorship and scope.
