## Parent PRD

`issues/prd.md`

## What to build

The tracer bullet. One thin path through every stage, for exactly one claim against one document.

Commit a single real 10-K to the repo. Convert it to Markdown, build a tree, hardcode one claim (`"Revenue grew 140% year over year in FY2024"`), run a minimal verification agent with two tools against it, get the numbers back, compute the growth rate in Python, and print a verdict with its section path and a working sec.gov link.

No deck, no PDF, no claim extraction, no cache, no database, no API, no streaming, no BM25. Each of those is a later slice thickening a path that already works.

Wire the model client here: OpenAI-compatible, `LLM_BASE_URL` / `LLM_MODEL` / `LLM_API_KEY`, pointed at Groq or OpenRouter. Schema-constrained output, one retry on validation failure.

This slice is the schedule's canary. If it takes more than a day, the two-weekend estimate in the PRD is wrong, and that is worth knowing on day one.

## Acceptance criteria

- [ ] A real 10-K HTML filing is committed to the repo
- [ ] HTML converts to Markdown with tables intact as `| md | tables |` and headings as `#` levels
- [ ] Tree builder produces a section tree containing `Item 8` with a `Consolidated Statements of Operations` child
- [ ] Each node carries `node_id`, `title`, `summary`, and an address — and **no text**
- [ ] `get_structure` and `get_content` exist as callable functions with the return shapes described in the PRD
- [ ] `get_content` returns the income statement as a markdown grid with row labels and column years attached
- [ ] The agent locates the right node and returns two revenue figures plus a citation — and does **not** return a verdict
- [ ] Growth rate is computed in Python; no arithmetic is asked of the model
- [ ] CLI prints: claim, verdict, both figures, section path, sec.gov URL
- [ ] That URL lands on the cited text in the real filing
- [ ] Provider is swappable by environment variable with no code change
- [ ] Malformed model output retries once, then fails the claim rather than the run

## Blocked by

None — can start immediately.

## User stories addressed

- User story 4
- User story 8
- User story 10
- User story 14
- User story 17
