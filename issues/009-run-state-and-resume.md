## Parent PRD

`issues/prd.md`

## What to build

Run state in MongoDB, and resumption after a crash.

Each claim's status and verdict is recorded as it completes. A killed run restarts at the first incomplete claim group and never repeats completed work. Tree building is already cached by content hash from `issues/002`, so a resumed run pays for neither trees nor summaries.

Verifiable rather than asserted: kill a run at the halfway mark, restart it, and confirm both that no completed claim is reprocessed and that the final result matches an uninterrupted run.

Mongo access stays inside one thin module, so the ceilings section can name the exact interface where this would be swapped at scale.

## Acceptance criteria

- [ ] Run state records `run_id`, `claim_id`, `status`, `verdict`
- [ ] State is written as each claim completes, not batched at the end
- [ ] A run killed at 50% and restarted resumes at the first incomplete claim group
- [ ] No completed claim is reprocessed on resume — verified by counting model calls, not by inspection
- [ ] The resumed run's final output matches an uninterrupted run's
- [ ] A resumed run rebuilds no trees and regenerates no summaries
- [ ] Run state is inspectable while a run is in progress
- [ ] All Mongo access is confined to one module

## Blocked by

- Blocked by `issues/004-verification-agent.md`

## User stories addressed

- User story 29
- User story 30
- User story 31
