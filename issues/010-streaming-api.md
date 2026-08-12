## Parent PRD

`issues/prd.md`

## What to build

FastAPI with SSE. Verdicts stream as they are produced rather than arriving in one batch at the end.

Because claims are verified in groups of roughly ten, results emit per group — the first group's verdicts appear while later groups are still being investigated. An analyst starts reading before the run finishes.

Progress is visible: which group is in flight, how many claims remain. The agent's reasoning trace streams too, since watching the system decide where to look is the demo.

The API stays thin. Orchestration only, no logic of its own.

## Acceptance criteria

- [ ] FastAPI endpoint accepts a deck plus a corpus and returns an SSE stream
- [ ] Verdicts emit per claim group, not batched to the end of the run
- [ ] First verdict appears within seconds of the run starting
- [ ] Progress events show claims completed and remaining
- [ ] Agent reasoning and tool calls stream as events
- [ ] A CLI client consumes the stream and renders it readably
- [ ] The API module contains no verification, arithmetic, or verdict logic
- [ ] A run assertion confirms every claim received a verdict before the stream closes

## Blocked by

- Blocked by `issues/005-decision-engine.md`

## User stories addressed

- User story 5
- User story 6
- User story 7
- User story 11
