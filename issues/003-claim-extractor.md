## Parent PRD

`issues/prd.md`

## What to build

Turn the deck into a typed claim set. One query over the whole deck tree, all claims at once — not a per-page loop.

Because the query runs over the tree, a claim on a slide that omits its period inherits that period from its ancestor section node. A slide reading *"Revenue grew 140%"* under a *"FY2024 Financial Highlights"* parent extracts with `period: FY2024` attached, rather than as an unverifiable fragment.

Unfalsifiable content is discarded here, at extraction, and never enters the pipeline. Superlatives, market-size assertions, forward-looking projections, and team-quality claims never appear in results, are never retrieved for, and are never counted as anything.

Slides that yield no extractable text — chart images with no text layer — are counted and reported rather than silently skipped.

## Acceptance criteria

- [ ] One model call over the deck tree returns all claims; no per-page loop
- [ ] Each claim carries: text, type, period, deck page, and source node
- [ ] Claim types cover absolute figure, derived figure, ratio, entity existence, and count
- [ ] A claim whose slide omits the period inherits it from an ancestor node
- [ ] Superlatives, market-size, forward-looking, and team-quality claims are absent from the output
- [ ] Output validates against a Pydantic schema, with one retry on failure
- [ ] Slides yielding no text are counted and the count is reported, e.g. `"3 of 25 slides had no text layer"`
- [ ] Claims are chunked into groups of roughly ten for downstream verification
- [ ] Running against the committed demo deck produces a claim set that a human agrees is complete

## Blocked by

- Blocked by `issues/002-tree-builder-and-cache.md`

## User stories addressed

- User story 15
- User story 15b
- User story 16
- User story 17
- User story 20
