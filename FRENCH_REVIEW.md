# Upstream review for the French workstream

Review date: 18 November 2026. Source inspection and GitHub API review only;
the analyzer dependency environment and runtime benchmark have not been run.

## Reviewed baseline

- Upstream: [https://github.com/data-privacy-stack/presidio](https://github.com/data-privacy-stack/presidio).
- Source commit: [`fd78e974fbf9e15dad1f90de4fc125db39ef4200`](https://github.com/data-privacy-stack/presidio/commit/fd78e974fbf9e15dad1f90de4fc125db39ef4200).
- Analyzer package declares version `2.2.366` and Python `>=3.11,<3.15`.
- Review covers the checked-out main branch, not code in unmerged PRs. PR bodies
  and patches were inspected separately and remain work owned by their authors.

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

## Remaining questions before implementation

- Does the current draft sample or another contribution already cover the desired
  French examples when configured correctly?
- Which French number forms and speaker-role formats will v0.1 support, and how
  will incomplete, invalid, corrected or ambiguous answers be labelled?
- Should the French work extend the draft sample, provide a standalone sample,
  or ultimately become an opt-in recognizer? Core integration needs design review.
- Can the exact original-text spans be returned without leaking normalized
  sensitive values through explanations, telemetry or saved artifacts?

The roadmap records these as work, rather than claiming the French gaps have
already been reproduced or the feature is ready to release.
