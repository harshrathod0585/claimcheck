## Parent PRD

`issues/prd.md`

## What to build

The reproducible corpus, and `docker compose up`.

A fetch script pulls the demo documents from EDGAR — one company's 8-K EX-99.1 deck plus its 10-K and 10-Q — with a descriptive User-Agent and the required rate limit. The corpus itself is committed, so the demo never depends on the network or on EDGAR's mood.

Pre-built trees are committed alongside, so first run costs nothing. A sample run's verdicts are committed too, so a reviewer with no API key can still see a real result.

`docker compose up` brings up the app, Redis, and Mongo, and produces a working demo.

## Acceptance criteria

- [ ] Fetch script downloads deck, 10-K, and 10-Q from EDGAR by CIK
- [ ] Descriptive User-Agent set and the ≤10 req/sec limit respected
- [ ] Demo corpus committed to the repo
- [ ] Pre-built trees committed; a cold demo run builds no trees and generates no summaries
- [ ] A sample run's verdicts are committed and replayable with no API key
- [ ] `docker compose up` starts app, Redis, and Mongo and yields a working demo in one command
- [ ] README states plainly which paths need a key and which do not
- [ ] Native Markdown documents are accepted as corpus input alongside the fetched filings

## Blocked by

- Blocked by `issues/002-tree-builder-and-cache.md`

## User stories addressed

- User story 1
- User story 32
- User story 33
- User story 34
