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

## Runtime findings and current implementation

The registry and analyzer use `fr`, `PhoneRecognizer` uses `fr` and region `FR`,
and the threshold is `0.35`. `NoOpNlpEngine` supplies no NER/token/lemma model;
French context words are configured but receive no implicit text-context boost.
Core detection succeeds for written national and `+33` examples, but misses the
French spoken-digit, spoken-group and split-answer probes. The configured draft
also misses these spoken cases and adds an overlapping international span
omitting `+`. Quantity, price and missing-prompt negatives produce no matches.

See the [reproduction commands and complete case results](docs/samples/python/french_conversation_phone/index.md).
These eight cases are diagnostic, not an accuracy claim.

The first implementation supplied an independent French normalizer with the
draft's `(normalized_text, offset_map)` contract. The next step rechecked the
unchanged draft and cherry-picked it with crmarr's authorship and an origin
trailer (`4991494`). A trusted normalizer callback and optional bounded policy
extend that sample; legacy English detection defaults remain unchanged. The
synthetic CLI prints positions instead of values. No core recognizer, shared
default or canonical package dependency is changed.

French recognition now consumes prompts once, enforces speaker/boundary limits,
retains exact disjoint spans, and assigns explicit 0.7 validated / 0.2 review
scores. A separate review gate runs before combined Analyzer result de-duplication;
ambiguous/corrected/withdrawn answers withhold output rather than being hidden by
a generic phone score. Public Anonymizer replacement keeps agent turns intact
and removes the full international prefix. Unknown prompts and unmarked
corrections remain documented limitations, not a claim of anonymity.

Tests pass in the Python 3.11–3.14 CI matrix: 242 cases including the English tests,
100% coverage for French normalization and the configured recognizer, 94% across
sample modules and 96% of this stage's changed executable lines. Ruff passes for
the sample and analyzer. Source hashes and all eight diagnostic outcomes are in
[the new probe report](docs/samples/python/french_conversation_phone/conversation-probe-results.json).
These diagnostic probes alone are not an accuracy estimate. The full frozen
regression/resource evaluation and exact-source CI evidence are now available in
[the report](docs/samples/python/french_conversation_phone/reports/README.md).
Each CI job also passed two model-free core phone checks and 32 nearest anonymizer
checks; 25 model-dependent phone tests and full optional suites were not run.

The grammar, role/boundary policy and metrics were frozen before implementation:
[scope](docs/samples/python/french_conversation_phone/scope.md),
[fixture manifest](docs/samples/python/french_conversation_phone/fixtures/manifest.json).
The corpus is project-authored and synthetic: 100 positive and 120 negative
conversations, split by scenario family. Development positives checked initial
normalization. Release fixtures were first checked structurally and by hash,
then run as a full regression evaluation without changing the source/data pins or
threshold. Some release cases and all release families overlap known baseline/unit
probes, so this is project-authored regression evaluation, not independent or
unseen-family validation. The candidate matches all 120 annotated spans and all
220 expected outputs; all 80 baseline conversation failures remain in the report.

## Recipe contribution route (18 November 2026)

The user chose the [Recipes Gallery format](docs/recipes/CONTRIBUTING.md) over
prioritizing an animation and fork release. The new
[recipe](docs/recipes/french-phone-conversations/README.md) publishes the previously
external data-authoring procedure, imports the tested configuration and compares
exact-span precision/recall/F₂ plus mean recognition latency. The frozen corpus,
candidate pins and original evaluation report are unchanged. The historical
manifest is copied only after regenerated JSONL bytes match its hashes.

Proposed upstream title: `docs(recipes): evaluate French phone answers in support transcripts`.
The recipe itself adds scripts, documentation and CI coverage; it changes no
recognizer defaults, scores, package dependencies or versions.

Validation at `d6166b0`: all 248 sample/recipe tests pass locally and in
[CI on Python 3.11–3.14](https://github.com/NourMedjedel/presidio/actions/runs/44237271364).
The six recipe tests cover byte-for-byte regeneration, configuration/redaction,
recall-weighted F₂, saved-result immutability and runnable CLI steps. Recipe-code
coverage is 97%. A separate fresh clone and virtual environment passed install,
generation, configuration, full evaluation and saved-report derivation; only the
download cache was reused. The original frozen report's bytes are unchanged.

Upstream was rechecked before packaging: no matching French recipe was found;
draft #2316 remains open/unmerged at the same pinned head. **Dependency decision
still required:** the recipe imports helper modules supplied by this fork.
Do not submit a wrapper-only PR and imply it works with stock package files.
Prefer extending the existing draft/helper contribution first, or agree a
maintainer-approved recipe/helper layout with the original author credited.
Do not duplicate the English conversation engine in a second contribution.

Keep the submitted patch focused on recipe files and required registration/tests;
omit fork-only planning files and unrelated media. Core recognizer integration
would require a separate design decision and its mandatory YAML/export checks.
No upstream issue, comment or PR has been submitted by this fork.
