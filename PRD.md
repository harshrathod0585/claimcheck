# PRD — ClaimCheck

**Automated claim verification between an investor deck and a data room.**

Author: Harsh Rathod
Status: Draft v2 (supersedes `PRD-claimcheck.md`)
Primary artifact: a portfolio repository demonstrating engineering judgment to a reviewer at VectorShift (YC S23) — Backend / Forward Deployed Engineer.

---

## Problem Statement

A private-market investor receives a pitch deck from a company seeking capital, plus a data room of underlying documents — financial statements, filings, contracts. The deck is marketing material written by the seller. The data room is evidence.

An analyst must verify every claim in the deck against that evidence, across hundreds of pages, under deal-deadline pressure. It is slow, it is the highest-stakes reading in the deal, and it is exactly where a missed discrepancy costs the most.

Two things make it hard in practice, and both are unusual:

- **The numbers that matter live in tables.** A revenue figure is meaningless without its row label and its column year. Any tool that separates them produces confident nonsense.
- **Most discrepancies are not lies.** A deck reporting ARR against a filing reporting GAAP revenue is not deception — it is a different measurement. A tool that flags this as a contradiction is worse than no tool, because the analyst stops trusting it by the third false alarm.

VectorShift sells this capability in its own marketing: *"cross-references presentations against data rooms and flags inconsistencies."* This document specifies a working implementation, built on real public filings.

### A note on what this document is

This is a job-application project. The reader is one engineer with roughly ten minutes, not an analyst with a deal to close. That reframing is load-bearing throughout: it is why the scope is one company rather than five, why the honest-limitations section outranks the feature list, and why a 90-second recording at the top of the README is treated as a deliverable rather than a nicety.

Where product instinct and portfolio instinct conflict, portfolio wins, and the document says so rather than pretending otherwise.

## Solution

Given an investor presentation and a corpus of supporting filings, ClaimCheck identifies every factual claim in the presentation that the corpus **contradicts** or **fails to support**, and links each verdict to the exact location in the source filing.

The two design commitments that follow from the problem:

**Retrieval navigates structure instead of chopping it up.** SEC filings carry their own hierarchy — a table of contents, numbered items, named statement sections, and machine-readable table markup. ClaimCheck builds a tree from that existing structure and lets a model walk it the way a human analyst would: *"this claim is about revenue, so go to Item 8, then the Consolidated Statements of Operations."* Nothing is chunked, so no table is ever severed from its labels. This is still retrieval-augmented generation; what is replaced is vector similarity search, not RAG itself.

**Arithmetic happens in Python, never in the model.** The model locates and extracts numbers. Every growth rate, margin, and ratio is computed from those primitives in ordinary code. This removes an entire category of confidently-wrong output and makes the comparison logic unit-testable without an API key.

The differentiated output is a first-class `BASIS_MISMATCH` verdict: both figures found, both correct, measured on different accounting bases. Detecting this correctly — rather than crying fraud — is the difference between a demo and a tool.

## User Stories

### Running a verification

1. As a reviewer evaluating this repo, I want a single `docker compose up` to produce a working demo, so that I can judge the work without a setup session.
2. As a reviewer, I want a short recording at the top of the README showing verdicts streaming in, so that I can understand what this does in 90 seconds without cloning anything.
3. As a reviewer, I want the measured results table above the fold, so that I can see what was actually achieved before reading how it works.
4. As an analyst, I want to submit a deck and a set of evidence documents and get back a list of verdicts, so that I know which claims need my attention.
5. As an analyst, I want verdicts to stream as they are produced rather than arriving in one batch at the end, so that I can start reviewing while the run continues.
6. As an analyst, I want the first verdict to appear within seconds, so that I know the system is working and not hung.
7. As an analyst, I want to see which claim is currently being processed and how many remain, so that I can estimate when the run will finish.

### Trusting a verdict

8. As an analyst, I want every verdict to link directly to the exact location in the source filing, so that I can confirm it myself in one click.
9. As an analyst, I want to see the quoted evidence text alongside the verdict, so that I can judge it without leaving the results.
10. As an analyst, I want to see the section path the system navigated (`Item 8 › Consolidated Statements of Operations`), so that I understand why it looked where it looked.
11. As an analyst justifying a decision to my investment committee, I want the retrieval path in the output as a product feature rather than a debug log, so that I can show my work.
12. As an analyst, I want to see both the claimed figure and the actual figure side by side when they disagree, so that I can size the discrepancy immediately.
13. As an analyst, I want to know which accounting basis each figure was measured on, so that I can tell a real contradiction from a definitional difference.
14. As an analyst, I want the system to compute growth rates and margins in code rather than asking a model to do arithmetic, so that I can trust the numbers are not hallucinated.

### Claim handling

15. As an analyst, I want a claim on a slide that omits its period ("revenue grew 140%") to inherit the period from its section header, so that it can be verified rather than discarded as ambiguous.
15b. As an analyst, I want unfalsifiable marketing claims ("market-leading", "world-class team") discarded silently rather than flagged, so that my results list contains only things I can act on.
16. As an analyst, I want forward-looking projections excluded, so that the system does not flag a forecast for disagreeing with history.
17. As an analyst, I want absolute figures ("revenue was $4.2M in FY2024") checked against the income statement, so that the headline numbers are verified.
18. As an analyst, I want derived figures ("grew 140% YoY") checked by retrieving both endpoints and recomputing, so that a correct-looking percentage over wrong inputs is still caught.
19. As an analyst, I want ratios ("gross margin is 72%") recomputed from the statements, so that I catch a margin that is inconsistent with the figures it is derived from.
20. As an analyst, I want named-entity claims ("Acme Corp is a customer") checked across the whole corpus, so that a fabricated customer is caught.
21. As an analyst, I want a deck rounding $4,183,204 to "$4.2M" treated as correct, so that the system does not flag ordinary presentation rounding.
22. As an analyst, I want a period swap (an FY2023 figure labeled FY2024) caught, so that stale numbers presented as current are surfaced.
23. As an analyst, I want a unit error (millions stated as billions) caught, so that a thousand-fold overstatement is not missed because the digits match.

### Basis mismatch

24. As an analyst, I want a deck's ARR compared against a filing's GAAP revenue to be reported as a basis mismatch rather than a contradiction, so that I am not sent chasing a non-issue.
25. As an analyst, I want basis mismatches shown with both bases named explicitly, so that I can decide whether the deck's choice of metric is reasonable or self-serving.
26. As an analyst, I want basis mismatches counted separately in the summary, so that I can see at a glance whether this deck has real problems or just aggressive framing.

### Cost and resumption

27. As an operator, I want document structure cached by content hash, so that re-running after changing one document does not rebuild every tree.
28. As an operator, I want a second run over a mostly-unchanged corpus to cost a small fraction of the first, so that iterating is cheap.
29. As an operator, I want a killed run to resume at the first incomplete claim, so that a crash halfway through a long run does not waste the completed work.
30. As an operator, I want completed work never repeated on resume, so that I can verify resumption actually works rather than trusting it.
31. As an operator, I want run state inspectable while a run is in progress, so that I can debug a stuck run.

### Corpus

32. As a developer, I want a script that downloads real filings from EDGAR, so that the corpus is reproducible rather than a folder of mystery files.
33. As a developer, I want the demo corpus committed to the repo, so that the demo runs without network access or rate-limit surprises.
34. As a developer, I want pre-built document trees committed alongside the demo corpus, so that first-run cost does not gate the demo.
35. As a developer, I want a defect seeder that injects known errors into a real deck, so that I have exact ground truth to measure against.
36. As a developer, I want each defect category represented, so that I can report which kinds of error the system catches and which it misses.

### Spot check

37. As a reviewer, I want a count of how many seeded defects were caught out of how many were planted, so that I know the system works on more than the one example in the README.
38. As a reviewer, I want the misses listed with a one-line explanation of each, so that I can see the author knows where their own system fails.
39. As a reviewer, I want to know how many correct claims were falsely flagged, so that I can judge whether it cries wolf.
40. As a reviewer, I want the published third-party state of the art cited, clearly marked as a different task, so that I can see the author knows where this work sits.

### Honest limits

44. As a reviewer, I want a section naming exactly where this breaks at ten thousand documents, so that I can tell whether the author has thought past the demo.
45. As a reviewer, I want the document formats that are *not* supported stated plainly, so that I am not misled about generality.
46. As a reviewer, I want the swap points for single-node infrastructure identified by interface, so that I can see the author knows what would have to change.

## Implementation Decisions

### Scope

- **Two weekends, one company.** One deck plus that company's filings. Breadth across five companies teaches a reviewer nothing after the first and costs five times as much.
- **This is a demo, not a benchmarked system.** The point is to show a working implementation of the capability VectorShift advertises, built with visible judgment. It is not a research evaluation and does not pretend to be one. The measurement that survives is deliberately small — see below.
- **Cut order if time runs short:** entity-existence claims → resume-after-crash → streaming. Never cut the spot-check numbers or the honest-limitations section.
- The earlier draft's cut order was inverted: it cut `BASIS_MISMATCH` first. `BASIS_MISMATCH` is the most interesting part of the system and is now protected.

### Document formats

Three input formats, each doing the job it is suited to:

| Format | Role | Rationale |
|---|---|---|
| **HTML** | Evidence filings (10-K, 10-Q) | EDGAR publishes these as inline-XBRL HTML, not PDF. Section structure is in the markup, tables are real `<table>` elements, and every financial figure carries an inline XBRL tag. |
| **PDF** | The investor deck (8-K EX-99.1) | Genuine slide decks are filed as PDFs. They are short and sparsely laid out, so extraction is tractable, and page numbers genuinely exist. |
| **Markdown** | Any document, and the normalized intermediate | Lets a user drop in their own documents. Also the dump format for the structured representation, which makes the ingest layer inspectable by eye. |

The earlier draft's "text PDFs only" was wrong. Converting EDGAR HTML to PDF in order to parse it would destroy the structure the system depends on and then pay to reconstruct it badly.

Not supported: scanned or OCR documents, spreadsheets, audio.

### Citations

HTML filings have no pages, so the original goal of "cite a page number" does not survive contact with the source format. It is replaced by something better:

- **Primary citation is a deep link** into the filing on `sec.gov`, using the anchors present in EDGAR HTML, so a reader lands on the exact sentence in the authoritative document in one click.
- **Secondary citation is the section path** plus the exact quoted text.
- Deck-side citations remain page numbers, since the deck is a PDF and pages are meaningful there.

Restated goal: *every verdict links to the exact location in the source document, and the quoted text appears at that location.*

### Ingest — every document becomes a tree

All documents are ingested identically: loaded, structured, and turned into a tree. The deck is not special-cased.

This is a deliberate choice for symmetry. One loader, one tree builder, one cache path, no branch in the ingest code for "is this the deck." It also solves a real extraction problem for free — a slide reading *"Revenue grew 140%"* with no year on it inherits `FY2024` from its parent section node, where per-page extraction would have lost the period entirely and produced an unverifiable claim.

**The two trees are traversed differently, and this distinction must stay explicit in the code:**

| | Traversal | Why |
|---|---|---|
| **Deck tree** | **Exhaustive** — visit every leaf | Extraction must find *every* claim. A skipped leaf is a silently dropped claim, which is the worst available failure mode. |
| **Evidence trees** | **Selective** — descend one branch | Verification needs *the one* relevant section. Visiting everything would defeat the purpose and cost 200 pages per claim. |

Guard against a future "optimization" that turns the deck walk into a search. It would look like a speedup and would quietly lose claims.

Decks carry weaker structure than filings — visual layout rather than a machine-readable table of contents — so deck tree quality is expected to be lower, and the builder falls back to one-node-per-page when no structure is recoverable. That fallback is the previous per-page design, retained as a floor rather than a separate path.

### Verification — one agent, all claims, four tools

Claims are extracted first, then handed to a **verification agent** as a batch. The claims are the query; the document corpus is the environment the agent investigates through tools.

This is deliberately not one agent run per claim. Claims that share evidence share a fetch — a single income statement answers claims about revenue, growth, and gross margin at once, with one citation covering all three. Per-claim runs would re-fetch that table three times and lose the cross-claim reasoning entirely.

**Tools — four, no more:**

| Tool | Returns |
|---|---|
| `list_documents()` | Corpus index: doc_id, type, period covered |
| `search(query)` | BM25 across the corpus → candidate nodes. The only route for entity claims, which have no section to navigate to. |
| `get_structure(doc_id)` | The full tree — titles, summaries, addresses. **Never text.** |
| `get_content(doc_id, [node_ids])` | Selected nodes: markdown content with tables intact, plus `path` and a citation URL. Batched. |

Rejected: `get_summary` (already in `get_structure`) and `get_text` (duplicate of `get_content`).

**Two bounds, both guarding against silent claim loss rather than cost:**

- Claims are chunked into groups of roughly ten per agent run. Long trajectories cause open-weight models to drift and quietly finish having answered thirty of forty claims.
- `max_turns` is capped. Exceeding it fails the group loudly, never the run.
- Every claim is asserted to have a verdict before emission.

**The agent returns evidence, never verdicts.** Extracted numbers, node references, citation URLs, and its reasoning trace. Whether a claim is true is decided downstream in Python. That boundary is the project's central argument: it is why a mid-sized open-weight model suffices, and why the entire verdict layer is testable with no API key and no network.

### Retrieval

Tree navigation is implemented in this repository rather than delegated to a third-party service.

The mechanism is not exotic: read the document's own table of contents, build an outline of section → span, ask the model which branch is relevant, descend, and read the leaf. The bulk of the accuracy advantage over vector search comes from not severing tables from their labels — which structure-preserving navigation gets for free.

Building it rather than calling an API removes vendor availability, rate-limit, and per-document-cost risk, and means the project's headline capability is the author's own work. The trade is a timebox: the tree builder supports documents with parseable structure and **fails loudly on documents without it**. Every SEC filing has a table of contents. This limitation is stated in the README rather than hidden.

Routing, because tree navigation is strong within one structured document and weak at needle-in-haystack lookup across many:

| Claim type | Strategy |
|---|---|
| Absolute figure | Tree navigation → statement section |
| Derived figure / ratio | Tree navigation ×2 → compute in Python |
| Entity existence | BM25 across corpus → tree navigation on top hits |
| Headcount / segment | Tree navigation → Item 1 or segment note |

BM25 via `rank_bm25`: a few lines, no vector database, and strictly better than embeddings for exact proper nouns, which embeddings blur by design.

### XBRL

XBRL is a **second evidence channel**, not an answer key.

The earlier draft treated it as automatic ground truth. It cannot be: mapping the prose claim *"revenue grew 140% YoY"* onto the correct tag, period, and dimension is approximately the same problem the system exists to solve, and getting it wrong silently corrupts the labels. Using the problem to grade itself produces numbers that mean nothing.

Instead: the verifier may consult XBRL as a structured lookup alongside document retrieval, and "when does structured data beat reading the document?" becomes a reported finding. Ground-truth labels come from seeded defects (exact by construction) plus a small hand-curated set.

### Corpora

Reduced from three to two for v1.

| Corpus | Composition | Purpose |
|---|---|---|
| **A — Seeded** | One real deck, rewritten with ~15 deliberate defects | The spot check. Known answers, hand-counted. |
| **B — Real** | The same company's genuine deck and filings | The demo itself. Expected to yield basis mismatches, not fabrications. |

Dropped: the FinanceBench retrieval corpus. It measures single-document Q&A, which is not this task, and running it is a weekend that buys a number the README cannot honestly compare against anything.

Also dropped: the vector RAG baseline system. Building a second full pipeline in order to lose to it is a weekend of work for one table row. The architectural argument for structure-preserving retrieval is made in prose, with one worked example of a financial table severed by naive chunking — which costs an hour and makes the same point to a reader who already knows why chunking hurts tables.

**Corpus B's expected result is stated up front, not discovered.** A deck and a 10-K for the same period are produced by the same finance team from the same close, and non-GAAP figures are legally required to reconcile to GAAP inside the filing. There are very few lies to find. Finding eleven basis mismatches and zero fabrications is a legitimate reported finding — and it is precisely why `BASIS_MISMATCH` is a first-class verdict rather than an error case.

### Verdicts

| Verdict | Meaning |
|---|---|
| `SUPPORTED` | Evidence found and agrees within tolerance |
| `CONTRADICTED` | Evidence found and disagrees |
| `NO_EVIDENCE` | No supporting passage located |
| `BASIS_MISMATCH` | Both figures found, both correct, different accounting basis |

### Modules

Sketched for deep interfaces — substantial functionality behind a small surface that rarely changes. **This section needs the author's confirmation before implementation begins.**

| Module | Interface | Depth |
|---|---|---|
| **Loader** | `(bytes, format) → Document` | Absorbs all three-format messiness behind one normalized representation. PDF, HTML, and Markdown differences stop here and never leak downstream. |
| **Tree builder** | `Document → Tree` | Structure extraction and outline construction, for *every* document including the deck. Deterministic, no model calls, fully testable against committed fixtures. Falls back to one node per page when no structure is recoverable. |
| **Navigator** | `(Tree, query) → [Node]` | Selective descent for verification. The only retrieval module that calls the model. |
| **Extractor** | `Tree → [Claim]` | Exhaustive walk of the deck tree; each leaf yields typed claims, inheriting period and section context from ancestor nodes. The discard category is applied here rather than downstream. |
| **Router** | `Claim → Strategy` | Pure dispatch. Trivially testable, trivially extendable. |
| **Normalizer** | `text → Quantity` | Parses a figure into value, unit, scale, period, and basis. Pure function, no I/O, no model. |
| **Comparator** | `(Claim, [Quantity]) → Verdict` | All arithmetic, tolerance, and basis logic. Pure function. **The deepest and most valuable module in the system** — the entire verdict logic is testable with no API key and no network. |
| **Cache** | `hash → Tree` | Redis. Content-addressed by `sha256(file_bytes)`. |
| **Run state** | `(run_id, claim_id) → Status` | MongoDB. Enables resume. |
| **API** | FastAPI + SSE | Thin. Orchestration only, no logic of its own. |

The Normalizer/Comparator split is the design's centre of gravity. Pushing every unit, period, rounding, and basis decision into two pure functions means the parts most likely to be wrong are the parts easiest to test.

### Model

**Open-weight models only, served over an OpenAI-compatible endpoint.** No OpenAI, no Anthropic.

Provider is a config value, not a code dependency:

```
LLM_BASE_URL   # Groq or OpenRouter
LLM_MODEL
LLM_API_KEY
```

OpenRouter during development, for free model swapping. Groq for the recorded demo, because its inference speed is visible on camera and makes time-to-first-verdict trivially fast. Local Ollama works against the same interface for anyone who wants it, but is not the default.

Two reliability measures, since open-weight models are less dependable at structured output than hosted frontier models: **schema-constrained decoding** rather than asking for JSON in the prompt, and **validate-then-retry-once** with Pydantic, marking a claim failed rather than crashing the run.

The structural mitigation matters more than either: the model extracts text and picks branches, and does nothing else. It never performs arithmetic, never decides a verdict, never applies tolerance, and never constructs a citation. All of that is deterministic Python. That is what makes a mid-sized open-weight model sufficient for a task where a naive design would demand a frontier one — and it is the project's actual argument.

**Consequence for the demo:** an API key is now required for a live run. To keep the repository runnable by a reviewer who has no key, the demo corpus ships with pre-built trees *and* a recorded run's verdicts committed, so `docker compose up` replays a real result offline. Only fresh runs need a key. This is stated in the README rather than discovered.

### Infrastructure

Redis for the tree cache, MongoDB for run state.

Since the deployment target is local `docker compose`, the marginal cost of two containers is one line in a compose file — the user types the same single command either way. They also mirror VectorShift's own stack, which is legible to the reader at a glance.

The condition attached: both live behind thin, single-purpose modules, so the limitations section can identify the exact interface where each would be swapped at scale. Datastores smeared across the codebase would forfeit the benefit.

### Deployment

- **Local `docker compose up`** is the deliverable.
- **A 90-second recording** — terminal or asciinema — sits at the top of the README showing verdicts streaming in. Realistically the most-watched artifact in the repository, and treated as a first-class deliverable rather than documentation garnish.
- **No live hosted endpoint.** A public URL backed by per-call model spend is an open wallet on the author's credit card, and reviewers rarely click demo links. If one is ever added, it serves pre-computed results and makes no live model calls.

### The spot check

Not an evaluation harness. One script, one afternoon, three numbers.

Take the real deck, plant ~15 defects across the categories below, run the system, count by hand:

| Defect | Injection |
|---|---|
| Inflated figure | Revenue ×1.5 |
| Wrong growth rate | Correct endpoints, wrong percentage |
| Fabricated customer | Name absent from all filings |
| Wrong margin | Inconsistent with the income statement |
| Period swap | FY2023 figure labeled FY2024 |
| Unit error | Millions stated as billions |

Reported as three lines in the README: **caught N of 15**, **the misses, each with one line on why**, and **M correct claims falsely flagged**. No precision/recall/F1 vocabulary — the sample is far too small to support it, and dressing fifteen hand-counted cases in statistical language is the exact overclaiming this project should avoid.

The published third-party figure — VectifyAI's Mafin 2.5 at 98.7% on FinanceBench — is cited once, in prose, with its qualifications: it measures a full commercial product rather than an index layer, it is self-reported, and FinanceBench is single-document Q&A rather than cross-document contradiction-finding. Citing it correctly and declining to compare against it is the point.

## Testing Decisions

**What makes a good test here:** it asserts on external behavior — the verdict, the citation, the extracted quantity — and never on how the module reached it. A test that breaks when a prompt is reworded or a tree is restructured is testing the implementation and will be deleted the first time it cries wolf. Tests must run with no API key and no network; anything requiring a model call is a fixture, not a test.

**Tested, in priority order:**

1. **Comparator** — the highest-value tests in the repository. Every verdict rule: agreement within tolerance, disagreement, rounding bands, period swaps, unit errors, and each basis-mismatch case. Pure function, exhaustive table-driven cases, no mocking of anything.
2. **Normalizer** — figure parsing across the messy real forms: `$4.2M`, `4,183,204`, `(1,978)` for negatives, `FY2024` vs `Q4 2023`, percent versus basis points. Also table-driven.
3. **Tree builder** — against committed filing fixtures. Asserts the expected sections exist with correct spans and that anchors resolve. Deterministic, so this is a real test rather than a snapshot.
4. **Router** — claim type dispatches to the expected strategy. Small and cheap.
5. **Loader** — one fixture per format, asserting the normalized representation is equivalent across all three.
6. **Resume** — kill a run at 50%, restart, assert no completed claim is reprocessed and the final result matches an uninterrupted run. This is an integration test and the only one that needs the datastores running.

**Not unit-tested:** the Navigator and Extractor, both of which are model calls whose output varies. These are covered by the seeded spot check, which is the honest instrument for them. A mocked test of a model call asserts only that the mock was written.

**Scale note:** this is a demo, so the test suite is deliberately small — the Comparator and Normalizer tests exist because that logic is fiddly and cheap to get wrong, not because the repo is aiming for coverage. Everything else gets one test or none.

**Prior art:** none — this is a new repository. The convention established here is plain `pytest`, table-driven cases via `parametrize`, fixtures committed as real filing excerpts rather than hand-written synthetic ones.

## Out of Scope

- Any UI beyond the streaming CLI and HTTP demo
- Authentication, multi-tenancy, persistence of past deals
- Scanned or OCR documents, spreadsheets, audio
- General question-answering over the corpus — verification only
- Judgement on unfalsifiable claims: superlatives, market-size assertions, forward-looking projections, team-quality claims. Discarded silently, never flagged.
- Cross-document entity resolution
- Incremental re-indexing on partial document edits
- A hosted public demo endpoint
- FinanceBench retrieval evaluation
- A vector RAG baseline system built for comparison
- Precision, recall, F1, or any statistical framing of a fifteen-case sample
- Cost, latency, and percentile instrumentation
- Multi-company corpus breadth
- Matching or claiming to match the published commercial state of the art

## Further Notes

### Open questions carried forward

These were reached but not settled during design and remain genuinely open:

1. **Rounding tolerance band.** A deck stating "$4.2M" against a filing's $4,183,204 is not a defect. The exact band — relative, absolute, or scale-dependent — is unresolved. It belongs entirely inside the Comparator, so it is cheap to change and cheap to test.
2. **Confidence threshold for surfacing a flag.** Is a missed defect worse than a false alarm? Probably yes: an analyst re-checks a false alarm in seconds but never sees a miss. Not yet committed.
3. **Whether `NO_EVIDENCE` is surfaced or only logged.** Data rooms are legitimately incomplete, and a wall of `NO_EVIDENCE` would drown the real findings.
4. **The `BASIS_MISMATCH` detection rule itself.** Distinguishing "different basis" from "wrong number" is the system's hardest judgement and its most valuable output. Approach not yet chosen.
5. **Claim extraction schema and prompt design.** Deferred pending the above.

### Risks

| Risk | Mitigation |
|---|---|
| Tree building on 200-page filings is slow | Cache by content hash; commit pre-built trees for the demo corpus |
| Claim extraction over-fires on marketing prose | Typed extraction with an explicit discard category; measure and report the false-positive rate |
| Tree navigation is weak at cross-document entity lookup | BM25 pre-filter, designed in rather than patched on |
| The real corpus contains no genuine contradictions | Expected and stated in advance; Corpus A carries the measurement, Corpus B carries realism |
| Basis mismatches swamp the results | `BASIS_MISMATCH` is a first-class verdict, not an error |
| The self-built tree builder underperforms | Timeboxed and scoped to structured filings; failure mode is loud and documented |
| Two weekends is optimistic | Cut order is fixed in advance and protects the evaluation over the features |

### README structure

1. The 90-second recording
2. The problem, in two sentences
3. The spot-check numbers — caught, missed, falsely flagged
4. Why structure-navigating retrieval, with the severed-table example
5. Architecture diagram
6. **Where this breaks at your scale** — tree-build cost at ten thousand documents, model spend per run, no cross-document entity resolution, no incremental re-index, single-node Redis, and the exact module interfaces where each swap would happen

Section 6 matters more than sections 3 through 5. Naming one's own ceilings is the strongest available signal that the work was done by someone who has thought past the demo.
