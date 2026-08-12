## Parent PRD

`issues/prd.md`

## What to build

The verification agent, and the four tools it investigates the corpus with.

A group of roughly ten claims is the query. The document corpus is the environment. The agent orients itself with `list_documents`, picks a filing, reads its tree with `get_structure`, fetches the nodes it selected with `get_content`, and repeats until it has evidence for every claim in the group.

The agent reasons **across** claims. One fetch of the income statement should answer claims about revenue, growth, and gross margin together, citing the same node for all three.

The agent returns evidence — extracted numbers, node references, citation URLs, and its reasoning trace. **It never returns a verdict.** Deciding whether a claim is true happens downstream in `issues/005`, in Python.

## Acceptance criteria

- [ ] Four tools exist: `list_documents`, `search`, `get_structure`, `get_content` — and no others
- [ ] `get_structure` returns titles, summaries, and addresses, never text
- [ ] `get_content` accepts a list of node ids and returns them in one call, with tables intact and a citation URL per node
- [ ] A group of ten claims is verified in a single agent run
- [ ] Claims sharing evidence resolve from one fetch, citing the same node
- [ ] The agent output contains extracted values and citations, and contains no verdict field
- [ ] `max_turns` is capped; exceeding it fails the group with a clear error and leaves other groups unaffected
- [ ] The reasoning trace is captured as output, not logged and discarded
- [ ] Every claim in a group comes back with an evidence record, even if that record is "nothing found"
- [ ] An assertion fails the run if any claim is missing from the agent's output
- [ ] Multi-hop works: a claim whose evidence sits behind a `See Note 14` reference is resolved

## Blocked by

- Blocked by `issues/003-claim-extractor.md`

## User stories addressed

- User story 8
- User story 9
- User story 10
- User story 11
- User story 12
