# French conversation-aware phone redaction

This fork develops an opt-in Presidio extension for French phone numbers expressed
in conversation, including spoken groups and answers split across speaker turns.
Owner: Nour Medjedel. Arabic is deferred until after the French release.

**Current status (18 November 2026):** M0–M3 completed. The sample recognizes and
redacts bounded French phone answers with a separate review gate. The exact-source
CI matrix passes on Python 3.11–3.14: 242 sample tests, two model-free upstream
phone checks and 32 anonymizer checks per job. Combined sample coverage is 94%;
this stage's changed-line coverage is 96%.

The frozen full corpus produced 120/120 exact spans and 220/220 expected outputs
for the extension, versus 20/120 spans and 140/220 outputs for the configured core.
Source/data pins, every baseline failure and measurements are published in
[the report](docs/samples/python/french_conversation_phone/reports/README.md).
These are narrow project-authored synthetic regression results with known probe
overlap, not independent or production validation. M4 recording/release review
remains open; no French release tag has been created.

[Run the sample and reproduce the baseline](docs/samples/python/french_conversation_phone/index.md).
[Frozen grammar and evaluation policy](docs/samples/python/french_conversation_phone/scope.md).

## Scope of v0.1

- Input: text transcripts with explicit speaker roles, in French (`fr`).
- Phone region: France (`FR`), national form and `+33`.
- Entity: `PHONE_NUMBER` only, through an additive, self-contained sample first.
- Detect the declared French digit/group grammar and bounded multi-turn answers.
- Preserve original offsets and unrelated turns; provide explainable scores and
  non-reversible redaction through Presidio's public interfaces.
- Run locally on CPU without a hosted model, paid API or GPU requirement.

This does not replace Presidio's existing phone recognizer, add all French PII
types, provide speech recognition or promise complete anonymization. Swiss and
Belgian regions, broader francophone number forms, other identifiers and Arabic
implementation are separate follow-ups.

## Milestones

Work proceeds by acceptance gates, not invented deadlines. M0–M3 are complete;
M4 and Arabic remain open. A milestone is complete only when its linked criteria
are met.

| Milestone | Issues | Exit criteria |
| --- | --- | --- |
| [M0 - French baseline and scope](https://github.com/NourMedjedel/presidio/milestone/1) | [#1](https://github.com/NourMedjedel/presidio/issues/1), [#2](https://github.com/NourMedjedel/presidio/issues/2) | Pin upstream, reproduce the remaining French conversation gaps, review overlapping PRs, and freeze the supported grammar and evaluation rubric. Implementation starts only if a gap remains. |
| [M1 - French numbers and exact text spans](https://github.com/NourMedjedel/presidio/milestone/2) | [#3](https://github.com/NourMedjedel/presidio/issues/3) | Parse the declared French spoken-phone grammar locally, preserving an exact mapping to the original text. No GPU, hosted model or paid API dependency. |
| [M2 - Conversation-aware phone redaction](https://github.com/NourMedjedel/presidio/milestone/3) | [#4](https://github.com/NourMedjedel/presidio/issues/4), [#5](https://github.com/NourMedjedel/presidio/issues/5) | Recognise prompted French phone answers across bounded speaker turns. Keep each request stateless and return exact, disjoint spans with explainable scores. |
| [M3 - Presidio integration and release evaluation](https://github.com/NourMedjedel/presidio/milestone/4) | [#6](https://github.com/NourMedjedel/presidio/issues/6), [#7](https://github.com/NourMedjedel/presidio/issues/7), [#8](https://github.com/NourMedjedel/presidio/issues/8), [#9](https://github.com/NourMedjedel/presidio/issues/9) | Verify public Analyzer/Anonymizer and French configuration paths, negative cases, English compatibility, privacy, resource limits and reproducible measurements. |
| [M4 - Publish French v0.1 sample](https://github.com/NourMedjedel/presidio/milestone/5) | [#10](https://github.com/NourMedjedel/presidio/issues/10), [#11](https://github.com/NourMedjedel/presidio/issues/11) | Ship an offline demo, installation instructions, limitations and an honestly labelled evaluation report. Tag a fork release only after the gates pass; prepare a small attributable upstream contribution. |
| [Later - Arabic discovery after French v0.1](https://github.com/NourMedjedel/presidio/milestone/6) | [#12](https://github.com/NourMedjedel/presidio/issues/12) | Deferred research only. Review Unicode-digit and Arabic work upstream, choose a language variety and phone region, and define a separate evaluation set after the French release. |

## Work items and dependencies

The issue bodies contain the deliverables, tests and acceptance criteria.

| Issue | Deliverable | Depends on |
| --- | --- | --- |
| [#1](https://github.com/NourMedjedel/presidio/issues/1) | Audit current French support and reproduce the remaining conversation gap | None |
| [#2](https://github.com/NourMedjedel/presidio/issues/2) | Freeze the French phone grammar, annotation rules and evaluation corpus | #1 |
| [#3](https://github.com/NourMedjedel/presidio/issues/3) | Implement French spoken-phone normalization with original-text offsets | #2 |
| [#4](https://github.com/NourMedjedel/presidio/issues/4) | Recognize French phone prompts and bounded answers across speaker turns | #3 |
| [#5](https://github.com/NourMedjedel/presidio/issues/5) | Return exact disjoint spans and explainable recognition scores | #4 |
| [#6](https://github.com/NourMedjedel/presidio/issues/6) | Verify French public configuration and Analyzer-to-Anonymizer integration | #5 |
| [#7](https://github.com/NourMedjedel/presidio/issues/7) | Add false-positive, privacy-boundary and English compatibility regressions | #6 |
| [#8](https://github.com/NourMedjedel/presidio/issues/8) | Bound input processing and keep demo outputs free of raw PII telemetry | #6 |
| [#9](https://github.com/NourMedjedel/presidio/issues/9) | Publish a reproducible baseline-versus-French evaluation report | #7, #8 |
| [#10](https://github.com/NourMedjedel/presidio/issues/10) | Create the offline French demo, usage guide and short README recording | #9 |
| [#11](https://github.com/NourMedjedel/presidio/issues/11) | Release fr-conversation-v0.1.0 and prepare an attributable upstream contribution | #10 |
| [#12](https://github.com/NourMedjedel/presidio/issues/12) | Define the Arabic extension after the French release and review existing upstream work | #11 |

## Next action

Add #10's short README recording using the tested synthetic split-answer and
review scenarios. Then complete #11's release review and fresh-install checks
before tagging the fork sample. Keep benchmark scope and limitations visible.
An upstream contribution remains a separate attributable proposal, not an
automatic consequence of a fork release.

The [draft conversation sample](https://github.com/data-privacy-stack/presidio/pull/2316)
was rechecked and cherry-picked with original authorship and an origin trailer.
Its English defaults are retained; French uses an opt-in callback and bounded
policy. The `+33` overlap case now produces one complete span and clean anonymizer
output in the combined registry. Core phone defaults are unchanged.

Already solved: French-region typo #2008/#2009 and normalization interface #2397.
Do not reopen them. NIR #2314 and SIREN/SIRET #2321 remain outside this scope;
Unicode digits #2480 and Arabic #2422 are deferred integration work. See the
[source review](FRENCH_REVIEW.md) for linked status and reuse decisions.

## Frozen release gates (not yet achieved)

The detailed rubric and input bounds were frozen in M0, before implementation
or tuning, in [scope.md](docs/samples/python/french_conversation_phone/scope.md):

- At least 100 synthetic positive and 100 negative conversations, with exact
  original-text spans. Separate release and development cases by scenario family.
- Target: at least 95% exact-span precision and recall on the frozen
  release set, and every named critical regression case passing. These are
  frozen targets, not achieved results or production guarantees.
- Measure whole-conversation redaction success, false positives by scenario,
  supported grammar, latency on stated CPU hardware, and remaining failures.
- No hidden retries, threshold retuning on release cases or deletion of failures.
- At least 90% coverage on changed executable lines; compatible supported Python
  versions and no unrelated changes to English defaults.
- Analyzer-to-Anonymizer tests and real French configuration-path coverage.
- No PII values in telemetry, errors or score explanations; documented input
  bounds, request isolation and best-effort limitations.
- Fresh-install instructions, a local demo and reproducible evaluation artifacts.

Project-authored synthetic cases remain project-authored. Document any independent
review honestly; do not describe synthetic results as production validation.

## Reuse and contribution strategy

The upstream draft conversation sample already addresses related English cases.
Inspect its latest state before coding, reuse where appropriate, preserve its
MIT attribution and coordinate the integration shape before proposing core changes.
Keep the recognizer stateless between requests; conversation tracking is local to
one supplied transcript. Never change existing patterns or scores as a side effect.

Follow `AGENTS.md`, `CONTRIBUTING.md` and applicable `.github/instructions/`.
Use uv and commit lockfile changes with dependency changes. Do not edit
`CHANGELOG.md`; upstream release entries are generated. When contributing a
sample, update the samples index and MkDocs navigation together.

The planned fork tag is `fr-conversation-v0.1.0`, after the gates pass. Do not
publish a replacement under Presidio's canonical package name or imply upstream
endorsement. Prepare small, focused upstream contributions separately; a fork
release and an upstream merge are different outcomes.

Keep fork-only planning files out of a future focused upstream code PR, for
example by starting that feature branch from the appropriate upstream base and
selectively committing the implementation and required tests/docs.

## Arabic later

After French v0.1, recheck current Unicode-digit and Arabic contributions. Choose
a language variety and phone region explicitly, then build a separately reviewed
corpus and baseline. Do not assume French grammar can be translated directly.
