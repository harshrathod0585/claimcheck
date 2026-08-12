## Parent PRD

`issues/prd.md`

## What to build

**HITL.** The two highest-leverage artifacts in the repository. Neither should be auto-generated.

**The recording.** Ninety seconds, terminal or asciinema, at the very top of the README. It shows the agent orienting, calling tools, and verdicts streaming in. Realistically the most-watched thing in the project — most reviewers will watch it and never clone. Treat it as a deliverable, not documentation garnish.

**The ceilings section.** *"Where this breaks at your scale."* Tree-build cost at ten thousand documents. Model spend per run. No cross-document entity resolution. No incremental re-index on partial edits. Single-node Redis. Unbounded agent turns. Deck ingestion assumes recoverable structure. For each, name the module interface where the swap would happen.

Also in the README: the problem in two sentences, the spot-check numbers, why structure-navigating retrieval — argued with one worked example of a financial table severed by naive chunking — and an architecture diagram.

The published third-party figure (Mafin 2.5, 98.7% on FinanceBench) is cited once in prose with its qualifications: full commercial product not an index layer, self-reported, and a different task. Cited correctly, not compared against.

Section order matters. The ceilings section outranks the feature description.

## Acceptance criteria

- [ ] 90-second recording embedded at the top of the README, showing tool calls and streaming verdicts
- [ ] Problem stated in two sentences
- [ ] Spot-check numbers present: caught, missed with reasons, falsely flagged
- [ ] Retrieval argument made with a concrete severed-table example, not assertion
- [ ] Architecture diagram included
- [ ] Ceilings section names every limitation above, each with the interface where it would be swapped
- [ ] Mafin 2.5 figure cited once with all three qualifications, and not used as a comparison
- [ ] Unsupported formats stated plainly: no scanned documents, no OCR, no spreadsheets
- [ ] README states which paths require an API key and which replay committed results
- [ ] No claim in the README is unsupported by something in the repo

## Blocked by

- Blocked by `issues/010-streaming-api.md`
- Blocked by `issues/012-spot-check.md`

## User stories addressed

- User story 1
- User story 2
- User story 3
- User story 40
- User story 44
- User story 45
- User story 46
