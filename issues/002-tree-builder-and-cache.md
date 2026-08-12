## Parent PRD

`issues/prd.md`

## What to build

Promote the skeleton's inline tree building into a real ingest stage that handles all three formats and caches its output.

Every document — deck PDF, EDGAR HTML, native Markdown — goes through one loader and one tree builder. HTML converts to Markdown first, preserving heading levels, table structure, and the original `id` attributes needed for citation. The builder scans for a table of contents, splits into size-bounded nodes, generates a short summary per node, and attaches an address appropriate to the format.

Trees are cached by `sha256(file_bytes)` in Redis, so a document is built once ever. Summary generation is the only model call in ingest and is cached along with the tree.

The builder must fail loudly on documents with no recoverable structure rather than producing a garbage tree.

## Acceptance criteria

- [ ] One loader handles PDF, HTML, and Markdown, producing a normalized document
- [ ] HTML → Markdown preserves tables as markdown grids and headings as `#` levels
- [ ] Original HTML `id` attributes survive conversion and land on the corresponding node
- [ ] Address per format: PDF → page range, Markdown → `line_num`, HTML-derived → line_num plus anchor
- [ ] Node split respects the size bounds from the PRD (≈10 pages, ≈20k tokens)
- [ ] Each node carries a summary of roughly 100 tokens, describing contents — nouns, metrics, entities, periods — not narrative
- [ ] Node text is **not** stored in the tree
- [ ] The full tree of a 200-page filing serialises small enough to fit in a single prompt
- [ ] Tree cached in Redis under `sha256(file_bytes)`; second ingest of the same bytes makes zero model calls
- [ ] A document with no recoverable table of contents or heading structure raises a clear error naming the file
- [ ] Cache access is confined to one thin module

## Blocked by

- Blocked by `issues/001-walking-skeleton.md`

## User stories addressed

- User story 27
- User story 28
- User story 45
