## Parent PRD

`issues/prd.md`

## What to build

The `search` tool, and entity-existence claims.

*"Acme Corp is a customer"* has no section to navigate to. The name could appear in a contract exhibit, a subsidiary list, MD&A, or nowhere at all. Tree descent handles this badly — there is no summary that says "contains the word Acme."

BM25 across the corpus via `rank_bm25`. A few lines, no vector database, and strictly better than embeddings for exact proper nouns, which embeddings blur by design. The agent calls `search`, gets candidate nodes across all documents, then reads the top few.

A fabricated customer — a name absent from every filing — must come back as unsupported rather than silently missing.

## Acceptance criteria

- [ ] `search(query)` returns scored candidate nodes across the whole corpus
- [ ] Index built over node content at ingest, cached alongside the tree
- [ ] Entity claims route through `search` before any tree read
- [ ] A customer named in the deck and present in the filings resolves as supported, citing where it was found
- [ ] A fabricated name absent from all filings resolves as unsupported, not skipped
- [ ] Exact proper-noun matching works where the name appears in a table or exhibit list
- [ ] Search covers all documents in the corpus, not just the one selected for figure claims

## Blocked by

- Blocked by `issues/004-verification-agent.md`

## User stories addressed

- User story 20
