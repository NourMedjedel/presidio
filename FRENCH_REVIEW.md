# Upstream review for the French workstream

Review date: 18 November 2026. Source inspection, a refreshed GitHub API review,
and an eight-case model-free runtime probe. This is gap reproduction, not a
representative benchmark. The French redaction release has not been evaluated.

## Reviewed baseline

- Upstream: [https://github.com/data-privacy-stack/presidio](https://github.com/data-privacy-stack/presidio).
- Source commit: [`fd78e974fbf9e15dad1f90de4fc125db39ef4200`](https://github.com/data-privacy-stack/presidio/commit/fd78e974fbf9e15dad1f90de4fc125db39ef4200).
- Analyzer package declares version `2.2.366` and Python `>=3.11,<3.15`.
- Runtime: Python 3.12.14, analyzer 2.2.366, phonenumbers 9.0.41, spaCy 3.8.16,
  locked core/development dependencies. No optional hosted/GPU integrations.
- The core probe uses source main; the separate draft comparison pins #2316 head
  `ddfd1893dd78e72f00a1100124d1738dbeab95e9`, by **crmarr**. Its module SHA-256
  and analyzer lock hash are recorded in
  [baseline-results.json](docs/samples/python/french_conversation_phone/baseline-results.json).

## Existing capabilities

1. [`PhoneRecognizer`](https://github.com/data-privacy-stack/presidio/blob/fd78e974fbf9e15dad1f90de4fc125db39ef4200/presidio-analyzer/presidio_analyzer/predefined_recognizers/generic/phone_recognizer.py)
   already includes `FR` in its default regions and uses `phonenumbers`.
   It takes a `supported_language` and custom context. A missing French registry
   or NLP configuration must not be mistaken for a new recognition capability.
2. [Language configuration](https://github.com/data-privacy-stack/presidio/blob/fd78e974fbf9e15dad1f90de4fc125db39ef4200/docs/analyzer/languages.md) separates NLP
   engines/models, language-specific recognizers and context. The default is
   English; French must be configured explicitly for a fair baseline.
3. [Opt-in text normalization](https://github.com/data-privacy-stack/presidio/blob/fd78e974fbf9e15dad1f90de4fc125db39ef4200/docs/analyzer/text_normalization.md)
   and [normalizer interfaces](https://github.com/data-privacy-stack/presidio/blob/fd78e974fbf9e15dad1f90de4fc125db39ef4200/presidio-analyzer/presidio_analyzer/text_normalizers/text_normalizer.py)
   already exist. Inspect and reuse these interfaces where appropriate rather
   than changing text globally and losing original offsets.
4. The public boundaries are Analyzer -> RecognizerResult -> Anonymizer. These
   contracts should carry exact original spans for disjoint customer answers.

## Related work and overlap decisions

| Work | State observed | Implication |
| --- | --- | --- |
| [Conversation issue #2315](https://github.com/data-privacy-stack/presidio/issues/2315), [sample PR #2316](https://github.com/data-privacy-stack/presidio/pull/2316) | Open issue; draft PR, not merged | English digit vocabulary, prompted card/SSN examples and configurable language. Reuse its design/code with attribution where appropriate; first reproduce the remaining French phone gap. |
| [French-region typo #2008](https://github.com/data-privacy-stack/presidio/issues/2008), [fix #2009](https://github.com/data-privacy-stack/presidio/pull/2009) | Closed/fixed | Do not reimplement. France is already in the core recognizer. |
| [French NIR PR #2314](https://github.com/data-privacy-stack/presidio/pull/2314) | Open, not merged | Do not duplicate social-security recognizer work. |
| [French SIREN/SIRET PR #2321](https://github.com/data-privacy-stack/presidio/pull/2321) | Open, not merged | Business identifiers are outside this phone-only release. |
| [Unicode-digit PR #2480](https://github.com/data-privacy-stack/presidio/pull/2480) | Open, not merged | Recheck before Arabic work; do not create a competing global digit fix. |
| [Arabic model sample #2422](https://github.com/data-privacy-stack/presidio/pull/2422) | Open, not merged | Existing model-side work belongs in the later Arabic review. |
| [Normalization PR #2397](https://github.com/data-privacy-stack/presidio/pull/2397) | Merged | A normalization interface is already in main; check compatibility before adding utilities. |

Source status was checked through GitHub's API. It can change; recheck the linked
PRs before implementation and before an upstream submission.

## Design constraints from the project

- [Agent guidance](https://github.com/data-privacy-stack/presidio/blob/fd78e974fbf9e15dad1f90de4fc125db39ef4200/AGENTS.md): modules processing records are stateless;
  preserve defaults and never log raw PII values. Conversation state may be
  request-local but must not persist on a recognizer between customers/calls.
- [Recognizer rules](https://github.com/data-privacy-stack/presidio/blob/fd78e974fbf9e15dad1f90de4fc125db39ef4200/.github/instructions/recognizers.instructions.md):
  accurate patterns/scores, exact offsets, lookalike negatives, explainability,
  ISO language codes and real configuration-path tests.
- [Contribution guide](https://github.com/data-privacy-stack/presidio/blob/fd78e974fbf9e15dad1f90de4fc125db39ef4200/CONTRIBUTING.md): additive, small contributions;
  preserve license/attribution, document behavior/security trade-offs and achieve
  at least 90% coverage on changed code. No hand-edited changelog entries.
- Samples require an entry in `docs/samples/index.md` and `mkdocs.yml`.
- Dependencies use uv; changes to package dependencies and their lockfile belong
  in the same commit. Heavy optional models are unnecessary for planning.

## Runtime findings and first implementation

The registry and analyzer use `fr`, `PhoneRecognizer` uses `fr` and region `FR`,
and the threshold is `0.35`. `NoOpNlpEngine` supplies no NER/token/lemma model;
French context words are configured but receive no implicit text-context boost.
Core detection succeeds for written national and `+33` examples, but misses the
French spoken-digit, spoken-group and split-answer probes. The configured draft
also misses these spoken cases and adds an overlapping international span
omitting `+`. Quantity, price and missing-prompt negatives produce no matches.

See the [reproduction commands and complete case results](docs/samples/python/french_conversation_phone/index.md).
These eight cases are diagnostic, not an accuracy claim.

The first implementation is an independent local French normalizer with the
draft's `(normalized_text, offset_map)` contract. It does not vendor the draft,
modify shared defaults, add a core recognizer or change package dependencies.
Samples index and MkDocs navigation are updated. Tests pass on Python 3.12.14:
135 cases, 100% coverage for the normalizer, 96% for the combined sample code;
Ruff passes for the sample and analyzer. Other supported Python versions and
full end-to-end redaction remain later gates.

The grammar, role/boundary policy and metrics were frozen before implementation:
[scope](docs/samples/python/french_conversation_phone/scope.md),
[fixture manifest](docs/samples/python/french_conversation_phone/fixtures/manifest.json).
The corpus is project-authored and synthetic: 100 positive and 120 negative
conversations, split by scenario family. Only development positives were used
to check normalization. Release fixtures were checked structurally and by hash,
not evaluated or used for tuning.

Next: reuse/rebase #2316 with attribution, add the French callback and bounded
conversation policy, then verify original disjoint spans and public redaction.
Core integration would need a separate design review. No upstream issue, comment
or PR has been submitted by this fork.
